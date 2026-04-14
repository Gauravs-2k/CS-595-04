from datetime import datetime

from weasyprint import HTML


def build_gap_report_html(session_payload: dict) -> str:
    patient = session_payload.get("patient", {})
    gaps = session_payload.get("gaps", [])
    created_at = session_payload.get("created_at", "")

    rows = "".join(
        [
            (
                "<tr>"
                f"<td>{g.get('severity', '')}</td>"
                f"<td>{g.get('category', '')}</td>"
                f"<td>{g.get('title', '')}</td>"
                f"<td>{g.get('description', '')}</td>"
                f"<td>{g.get('suggested_action', '')}</td>"
                "</tr>"
            )
            for g in gaps
        ]
    )

    return f"""
    <html>
      <head>
        <meta charset=\"utf-8\" />
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          h1 {{ margin-bottom: 6px; }}
          .meta {{ color: #444; margin-bottom: 16px; }}
          table {{ width: 100%; border-collapse: collapse; }}
          th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; text-align: left; }}
          th {{ background: #f3f4f6; }}
        </style>
      </head>
      <body>
        <h1>TransitionGuard Gap Report</h1>
        <div class=\"meta\">Patient: {patient.get('name', 'Unknown')} | DOB: {patient.get('dob', 'Unknown')} | Generated: {created_at}</div>
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Category</th>
              <th>Title</th>
              <th>Description</th>
              <th>Suggested Action</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </body>
    </html>
    """


def render_pdf(session_payload: dict, output_path: str) -> str:
    html = build_gap_report_html(session_payload)
    HTML(string=html).write_pdf(output_path)
    return output_path
