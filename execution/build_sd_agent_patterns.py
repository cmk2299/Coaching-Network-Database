#!/usr/bin/env python3
"""Aggregiere Berater-Patterns pro DM — welche Agenturen häufig genutzt.

Reads:  data/hire_history.json + data/persons_master.json
Output: data/sd_agent_patterns.json
"""
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
AGENT_BLACKLIST = {
    "ohne berater", "familienangehörige", "familienangehoerige",
    "eltern", "keine angabe", "kein berater",
    "-", "n/a", "unbekannt", "",
}


def main():
    hh = json.load(open(BASE / "data/hire_history.json"))["per_dm"]
    persons = json.load(open(BASE / "data/persons_master.json"))["persons"]
    # Curated trainer-agent overrides (TM doesn't expose agents on Trainer profiles)
    trainer_agents = {}
    ta_path = BASE / "data/trainer_agents.json"
    if ta_path.exists():
        try:
            trainer_agents = json.load(open(ta_path)).get("agents", {})
        except Exception:
            pass

    out = {}
    for dm_id, dm in hh.items():
        agents = defaultdict(list)
        for h in dm["hires"]:
            coach_tm = str(h["coach_tm_id"])
            cp = persons.get(coach_tm, {})
            agent = (cp.get("agent") or "").strip()
            # Fallback to curated trainer-agents
            if not agent or agent.lower() in AGENT_BLACKLIST:
                ta = trainer_agents.get(coach_tm) or {}
                agent = (ta.get("agent") or "").strip()
            if not agent or agent.lower() in AGENT_BLACKLIST:
                continue
            agents[agent].append(h["coach_name"])
        rels = [
            {"agent": a, "hires": len(coaches), "coaches": coaches}
            for a, coaches in sorted(agents.items(), key=lambda x: -len(x[1]))
            if len(coaches) >= 2
        ]
        if rels:
            out[dm_id] = {
                "name": dm["name"],
                "tier": dm.get("tier"),
                "club": dm.get("club"),
                "agent_relationships": rels,
            }

    json.dump({"per_dm": out}, open(BASE / "data/sd_agent_patterns.json", "w"),
              ensure_ascii=False, indent=2)
    print(f"✓ {len(out)} DMs mit Agent-Patterns (≥2 Hires/Agent)")
    if out:
        top = sorted(out.items(), key=lambda kv: -sum(r["hires"] for r in kv[1]["agent_relationships"]))[:5]
        for tm_id, d in top:
            agents_str = ", ".join(f"{r['agent']}({r['hires']})" for r in d['agent_relationships'][:3])
            print(f"    {d['name']:<28} → {agents_str}")


if __name__ == "__main__":
    main()
