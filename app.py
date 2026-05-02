from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import itertools

app = Flask(__name__)
CORS(app)

def get_adjacent(r, c, rows, cols):
    neighbors = []
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        if 0 <= nr < rows and 0 <= nc < cols:
            neighbors.append((nr, nc))
    return neighbors

def generate_world(rows, cols, num_pits):
    cells = [(r, c) for r in range(rows) for c in range(cols) if (r, c) != (0, 0)]
    random.shuffle(cells)
    pits = set(map(tuple, cells[:num_pits]))
    wumpus = cells[num_pits] if len(cells) > num_pits else None
    gold = cells[num_pits + 1] if len(cells) > num_pits + 1 else None
    return pits, wumpus, gold

def get_percepts(pos, pits, wumpus, rows, cols):
    r, c = pos
    adj = get_adjacent(r, c, rows, cols)
    breeze = any(tuple(a) in pits for a in adj)
    stench = wumpus is not None and tuple(wumpus) in [(ar, ac) for ar, ac in adj]
    return {"breeze": breeze, "stench": stench}

class KnowledgeBase:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.clauses = set()
        self.known_safe = set()
        self.inference_steps = 0

    def tell_no_hazard(self, r, c):
        self.clauses.add(("NOT_PIT", r, c))
        self.clauses.add(("NOT_WUMPUS", r, c))
        self.known_safe.add((r, c))

    def tell_breeze(self, r, c):
        adj = get_adjacent(r, c, self.rows, self.cols)
        clause = tuple(sorted([("PIT", ar, ac) for ar, ac in adj]))
        self.clauses.add(("BREEZE_IMPLIES", clause))

    def tell_no_breeze(self, r, c):
        adj = get_adjacent(r, c, self.rows, self.cols)
        for ar, ac in adj:
            self.clauses.add(("NOT_PIT", ar, ac))
            self.known_safe.add((ar, ac))

    def tell_stench(self, r, c):
        adj = get_adjacent(r, c, self.rows, self.cols)
        clause = tuple(sorted([("WUMPUS", ar, ac) for ar, ac in adj]))
        self.clauses.add(("STENCH_IMPLIES", clause))

    def tell_no_stench(self, r, c):
        adj = get_adjacent(r, c, self.rows, self.cols)
        for ar, ac in adj:
            self.clauses.add(("NOT_WUMPUS", ar, ac))

    def to_cnf(self):
        cnf = []
        for clause in self.clauses:
            if clause[0] == "NOT_PIT":
                cnf.append(frozenset([("NOT_PIT", clause[1], clause[2])]))
            elif clause[0] == "NOT_WUMPUS":
                cnf.append(frozenset([("NOT_WUMPUS", clause[1], clause[2])]))
            elif clause[0] == "BREEZE_IMPLIES":
                for lit in clause[1]:
                    cnf.append(frozenset([lit]))
            elif clause[0] == "STENCH_IMPLIES":
                for lit in clause[1]:
                    cnf.append(frozenset([lit]))
        return cnf

    def resolution_refutation(self, query_not_pit, query_not_wumpus, r, c):
        self.inference_steps = 0
        cnf = self.to_cnf()
        goals = []
        if query_not_pit:
            goals.append(frozenset([("PIT", r, c)]))
        if query_not_wumpus:
            goals.append(frozenset([("WUMPUS", r, c)]))
        for goal_clause in goals:
            clauses = list(cnf) + [goal_clause]
            proved = False
            new = set()
            while True:
                pairs = list(itertools.combinations(clauses, 2))
                for (ci, cj) in pairs:
                    self.inference_steps += 1
                    resolvents = self.resolve(ci, cj)
                    if frozenset() in resolvents:
                        proved = True
                        break
                    new.update(resolvents)
                if proved:
                    break
                if new.issubset(set(clauses)):
                    break
                clauses = list(set(clauses) | new)
            if not proved:
                return False
        return True

    def resolve(self, ci, cj):
        resolvents = set()
        for lit in ci:
            comp = self.complement(lit)
            if comp in cj:
                new_clause = (ci - frozenset([lit])) | (cj - frozenset([comp]))
                resolvents.add(frozenset(new_clause))
        return resolvents

    def complement(self, lit):
        if lit[0].startswith("NOT_"):
            return (lit[0][4:], lit[1], lit[2])
        else:
            return ("NOT_" + lit[0], lit[1], lit[2])

    def ask_safe(self, r, c):
        if (r, c) in self.known_safe:
            return True
        safe_pit = ("NOT_PIT", r, c) in self.clauses
        safe_wumpus = ("NOT_WUMPUS", r, c) in self.clauses
        if safe_pit and safe_wumpus:
            self.known_safe.add((r, c))
            return True
        return self.resolution_refutation(not safe_pit, not safe_wumpus, r, c)

sessions = {}

@app.route("/new_game", methods=["POST"])
def new_game():
    data = request.json
    rows = max(2, min(int(data.get("rows", 4)), 8))
    cols = max(2, min(int(data.get("cols", 4)), 8))
    num_pits = max(1, (rows * cols) // 5)
    pits, wumpus, gold = generate_world(rows, cols, num_pits)
    session_id = str(random.randint(100000, 999999))
    kb = KnowledgeBase(rows, cols)
    kb.tell_no_hazard(0, 0)
    percepts = get_percepts((0, 0), pits, wumpus, rows, cols)
    if percepts["breeze"]:
        kb.tell_breeze(0, 0)
    else:
        kb.tell_no_breeze(0, 0)
    if percepts["stench"]:
        kb.tell_stench(0, 0)
    else:
        kb.tell_no_stench(0, 0)
    sessions[session_id] = {
        "rows": rows, "cols": cols,
        "pits": [list(p) for p in pits],
        "wumpus": list(wumpus) if wumpus else None,
        "gold": list(gold) if gold else None,
        "agent_pos": [0, 0],
        "visited": [[0, 0]],
        "kb": kb,
        "alive": True,
        "won": False
    }
    safe_neighbors = [[nr, nc] for nr, nc in get_adjacent(0, 0, rows, cols) if kb.ask_safe(nr, nc)]
    return jsonify({
        "session_id": session_id,
        "rows": rows, "cols": cols,
        "agent_pos": [0, 0],
        "percepts": percepts,
        "safe_cells": [[r, c] for (r, c) in kb.known_safe],
        "visited": [[0, 0]],
        "safe_neighbors": safe_neighbors,
        "inference_steps": kb.inference_steps,
        "alive": True, "won": False,
        "message": "New game started. Agent at (0,0)."
    })

@app.route("/move", methods=["POST"])
def move():
    data = request.json
    session_id = data.get("session_id")
    target = data.get("target")
    if session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    s = sessions[session_id]
    if not s["alive"] or s["won"]:
        return jsonify({"error": "Game over"}), 400
    tr, tc = target
    rows, cols = s["rows"], s["cols"]
    pos = s["agent_pos"]
    adj = get_adjacent(pos[0], pos[1], rows, cols)
    if [tr, tc] not in [[r, c] for r, c in adj]:
        return jsonify({"error": "Not adjacent"}), 400
    kb = s["kb"]
    if not kb.ask_safe(tr, tc):
        return jsonify({
            "blocked": True,
            "inference_steps": kb.inference_steps,
            "message": f"KB says ({tr},{tc}) is NOT proven safe. Move blocked."
        })
    s["agent_pos"] = [tr, tc]
    if [tr, tc] not in s["visited"]:
        s["visited"].append([tr, tc])
    pits = set(map(tuple, s["pits"]))
    wumpus = tuple(s["wumpus"]) if s["wumpus"] else None
    if (tr, tc) in pits:
        s["alive"] = False
        return jsonify({
            "agent_pos": [tr, tc], "alive": False, "won": False,
            "inference_steps": kb.inference_steps,
            "message": "Fell into a pit! Game over.",
            "pits": s["pits"], "wumpus": s["wumpus"]
        })
    if wumpus and (tr, tc) == wumpus:
        s["alive"] = False
        return jsonify({
            "agent_pos": [tr, tc], "alive": False, "won": False,
            "inference_steps": kb.inference_steps,
            "message": "Eaten by the Wumpus! Game over.",
            "pits": s["pits"], "wumpus": s["wumpus"]
        })
    kb.tell_no_hazard(tr, tc)
    percepts = get_percepts((tr, tc), pits, wumpus, rows, cols)
    if percepts["breeze"]:
        kb.tell_breeze(tr, tc)
    else:
        kb.tell_no_breeze(tr, tc)
    if percepts["stench"]:
        kb.tell_stench(tr, tc)
    else:
        kb.tell_no_stench(tr, tc)
    won = s["gold"] and [tr, tc] == s["gold"]
    if won:
        s["won"] = True
    safe_neighbors = [[nr, nc] for nr, nc in get_adjacent(tr, tc, rows, cols) if kb.ask_safe(nr, nc)]
    return jsonify({
        "agent_pos": [tr, tc],
        "percepts": percepts,
        "safe_cells": [[r, c] for (r, c) in kb.known_safe],
        "visited": s["visited"],
        "safe_neighbors": safe_neighbors,
        "inference_steps": kb.inference_steps,
        "alive": True, "won": won,
        "blocked": False,
        "message": f"Moved to ({tr},{tc}). {'Found the gold! You win!' if won else ''}"
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
