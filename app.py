# app.py  —  Cloud Run API
import os
from flask import Flask, request, jsonify
from solver.core import solve

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/solve", methods=["POST"])
def solve_endpoint():
    try:
        p = request.get_json(force=True)
        results = solve(
            staff           = p["staff"],
            week_config     = p["week_config"],
            buffet_schedule = p["buffet_schedule"],
            bar_schedule    = p["bar_schedule"],
            time_limit      = int(os.environ.get("SOLVER_TIME_LIMIT", 60)),
        )
        return jsonify({"status": "success", "results": results})
    except KeyError as e:
        return jsonify({"status": "error", "message": f"Missing: {e}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
