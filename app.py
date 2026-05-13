# app.py  —  Cloud Run API
import io
import os
import tempfile
from flask import Flask, request, jsonify, send_file
from solver.core import solve
from reporter.excel import export_to_excel

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/upload", methods=["GET"])
def upload_form():
    return """
<!doctype html>
<html>
<head><title>Roster Solver</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 500px; margin: 60px auto; }
  h2   { color: #2F5597; }
  input[type=file] { margin: 12px 0; display: block; }
  button { background: #2F5597; color: white; padding: 10px 24px;
           border: none; border-radius: 4px; cursor: pointer; font-size: 15px; }
  button:hover { background: #1d3a7a; }
  p.hint { color: #666; font-size: 13px; }
</style>
</head>
<body>
  <h2>Roster Solver</h2>
  <form method="POST" enctype="multipart/form-data">
    <p class="hint">Upload your weekly Excel input file (week_NN.xlsx):</p>
    <input type="file" name="file" accept=".xlsx">
    <button type="submit">Run Solver &amp; Download Report</button>
  </form>
</body>
</html>
"""


@app.route("/upload", methods=["POST"])
def upload_and_solve():
    if "file" not in request.files or request.files["file"].filename == "":
        return "No file selected.", 400

    f = request.files["file"]
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            f.save(tmp.name)
            from data.excel_reader import load_from_excel
            staff, week_config, buffet_schedule, bar_schedule, daily_hours = \
                load_from_excel(tmp.name)
        os.unlink(tmp.name)
    except Exception as e:
        return f"Failed to read Excel file: {e}", 400

    time_limit = int(os.environ.get("SOLVER_TIME_LIMIT", 300))
    results = solve(
        staff           = staff,
        week_config     = week_config,
        buffet_schedule = buffet_schedule,
        bar_schedule    = bar_schedule,
        daily_hours     = daily_hours,
        time_limit      = time_limit,
    )

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as out:
        out_path = out.name
    export_to_excel(results, week_config, buffet_schedule, bar_schedule,
                    path=out_path)

    week = week_config.get("week_number", "XX")
    download_name = f"roster_week{week}.xlsx"

    def _cleanup(path):
        try:
            os.unlink(path)
        except OSError:
            pass

    response = send_file(
        out_path,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.call_on_close(lambda: _cleanup(out_path))
    return response


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
