"""Rapport PDF de scouting (reportlab) avec radar matplotlib ; couleurs = jetons de la charte."""
import io
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

TOK = {"navy": "#0B1F3A", "good": "#2EC4B6", "warn": "#E9B949", "bad": "#E4572E", "ink": "#16202E"}

def radar_png(labels, values):
    ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist(); v = values + values[:1]; ang += ang[:1]
    fig, ax = plt.subplots(figsize=(4.6, 4.6), subplot_kw={"polar": True}, dpi=160)
    ax.plot(ang, v, color=TOK["good"], lw=2); ax.fill(ang, v, color=TOK["good"], alpha=.25)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(labels, fontsize=7); ax.set_ylim(0, 10); ax.set_yticks([2.5, 5, 7.5, 10]); ax.tick_params(labelsize=6)
    b = io.BytesIO(); fig.savefig(b, format="png", bbox_inches="tight"); plt.close(fig); b.seek(0); return b

def build_pdf(gk_name, res, comment, model, versions, inputs, created):
    buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    ss = getSampleStyleSheet(); H = ParagraphStyle("h", parent=ss["Title"], textColor=colors.HexColor(TOK["navy"])); N = ss["BodyText"]
    f = res["final"]; el = [Paragraph(f"Rapport de scouting – {gk_name}", H), Paragraph(f"Évalué le {created} · versions des règles : {versions}", N), Spacer(1, 10)]
    lvl_col = TOK["good"] if f["level"] >= 5 else TOK["warn"] if f["level"] >= 3 else TOK["bad"]
    big = Table([[f"{f['score']:.1f} / 100", f"{f['level_label']}"]], colWidths=[7*cm, 7*cm])
    big.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(TOK["navy"])), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                             ("FONTSIZE", (0, 0), (-1, -1), 20), ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor(lvl_col)), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    el += [big, Spacer(1, 10)]
    subs = res["subscores"]; labs = [model.variables[k].label.replace("Sous-score ", "") for k in subs]
    rows = [["Sous-score", "Note /10"]] + [[l, f"{subs[k]['value']:.2f}"] for l, k in zip(labs, subs)]
    t = Table(rows, colWidths=[9*cm, 3*cm]); t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F2"))]))
    el += [t, Spacer(1, 8), Image(radar_png(labs, [subs[k]["value"] for k in subs]), width=8*cm, height=8*cm)]
    rel = res.get("reliability"); ap = res.get("age_potential")
    if rel: el.append(Paragraph(f"<b>Fiabilité</b> : indice {rel['index']:.2f} – marge d'incertitude ± {rel['margin']:.1f} points.", N))
    if ap and ap.get("potential") is not None: el.append(Paragraph(f"<b>Valeur immédiate</b> {ap['immediate']:.1f} · <b>Potentiel futur</b> {ap['potential']:.1f}", N))
    el += [Spacer(1, 6), Paragraph("<b>Règles principales activées (système principal)</b>", N)]
    for r in (res["trace"][model.cascade["final"]] or {})["fired_rules"][:5]:
        cond = " ET ".join(f"{model.variables[k].label} = {model.variables[k].term(v).label}" for k, v in r["if"].items())
        el.append(Paragraph(f"• SI {cond} ALORS {list(r['then'].values())[0]} (force {r['strength']:.2f})", N))
    el += [Spacer(1, 8), Paragraph("<b>Commentaire</b>", N), Paragraph(comment, N)]
    doc.build(el); return buf.getvalue()
