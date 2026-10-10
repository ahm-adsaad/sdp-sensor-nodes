"""Write tests/fixtures/ppk2_sample.csv in the Power Profiler export format. Run once:
    cd forecast && .venv/Scripts/python.exe tests/make_ppk2_sample.py
"""

import pathlib

rows = ["Timestamp(ms),Current(uA)"]
for i in range(0, 541):                      # 0 .. 5,400,000 ms
    t = i * 10000
    if t == 40000:
        rows.append("")                      # the app never writes blank rows, but a hand-edited file might
    rows.append(f"{t},{10000.0 if t < 3600000 else 30000.0:.3f}")
out = pathlib.Path(__file__).parent / "fixtures" / "ppk2_sample.csv"
out.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
print(out, len(rows) - 1, "rows")
