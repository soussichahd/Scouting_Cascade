"""Commentaire en langage naturel par gabarits (déterministe, sans LLM) + traceur."""
def _top_term(deg: dict, terms):
    return max(terms, key=lambda t: deg[t.id])

def comment(model, inputs, res) -> str:
    V = model.variables
    f = res["final"]; s = []
    s.append(f"Le gardien obtient une note de {f['score']:.1f}/100, ce qui correspond au {f['level_label']}.")
    subs = res["subscores"]
    names = {k: V[k].label.replace("Sous-score ", "") for k in subs}
    best = max(subs, key=lambda k: subs[k]["value"]); worst = min(subs, key=lambda k: subs[k]["value"])
    if best != worst:
        s.append(f"Son point fort est « {names[best]} » ({subs[best]['value']:.1f}/10), "
                 f"son point faible est « {names[worst]} » ({subs[worst]['value']:.1f}/10).")
    top = (res["trace"][model.cascade["final"]] or {}).get("fired_rules", [])
    if top:
        r = top[0]; parts = []
        for vid, tid in r["if"].items():
            v = V[vid]; parts.append(f"{v.label.lower()} {v.term(tid).label.lower()}")
        s.append("La règle la plus déterminante est : " + " et ".join(parts) + f" (force {r['strength']:.2f}).")
    rel = res.get("reliability")
    if rel:
        lab = "élevée" if rel["index"] >= 0.7 else "moyenne" if rel["index"] >= 0.4 else "faible"
        s.append(f"La fiabilité de l'observation est {lab} (indice {rel['index']:.2f}) : "
                 f"la note est à lire à ± {rel['margin']:.1f} points.")
    ap = res.get("age_potential")
    if ap and ap.get("potential") is not None:
        d = ap["potential"] - ap["immediate"]
        if d > 3: s.append(f"Son potentiel futur ({ap['potential']:.1f}) dépasse sa valeur actuelle : un profil à suivre.")
        elif d < -3: s.append(f"Sa valeur actuelle domine son potentiel futur ({ap['potential']:.1f}) : un profil immédiatement exploitable.")
        else: s.append(f"Son potentiel futur ({ap['potential']:.1f}) est proche de sa valeur actuelle.")
    return " ".join(s)
