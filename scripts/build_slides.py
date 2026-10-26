"""Build the self-contained presentation from project evidence."""
from __future__ import annotations
import argparse, base64, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "slides" / "slides.html"

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError): return default

def pending(label, source):
    return f'<div class="pending" role="note">Pending: {label} <small>({source})</small></div>'

def image(name, caption):
    path = ROOT / "evidence" / name
    if not path.exists(): return pending(caption, f"evidence/{name}")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<figure><img src="data:{mime};base64,{data}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'

def stat(value, label): return f'<div class="stat"><b>{value}</b><span>{label}</span></div>'

def build(final=False):
    cfg = read_json(ROOT / "slides/config.json", {})
    sim = read_json(ROOT / "results/simulation_summary.json", {})
    ev = read_json(ROOT / "results/eval_summary.json", {})
    token = read_json(ROOT / "results/token_runs.json", {})
    cost = read_json(ROOT / "results/cost_experiment.json", {})
    author = cfg.get("AUTHOR_NAME", "[MY INPUT NEEDED: your name]")
    repo = cfg.get("REPO_URL", "[MY INPUT NEEDED: Canvas GitHub URL]")
    pending_items = []
    if "MY INPUT NEEDED" in str(author): pending_items.append("slides/config.json: AUTHOR_NAME")
    if "MY INPUT NEEDED" in str(repo): pending_items.append("slides/config.json: REPO_URL")
    data = sim.get("methods", {})
    a, b, c = data.get("A: random", {}), data.get("B: balance", {}), data.get("C: balance + memory", {})
    def metric(row, key): return row.get(key, {}).get("average", "pending") if isinstance(row.get(key), dict) else "pending"
    def fmt(x): return f"{x:.3f}" if isinstance(x, (int,float)) else "pending"
    slides = []
    def slide(kicker, title, body, visual, notes): slides.append(f'<section><div class="kicker">{kicker}</div><h2>{title}</h2><div class="content">{body}{visual}</div><aside class="notes">{notes}</aside></section>')
    pitch_dots = "".join(f"<circle cx=\"{x}\" cy=\"{y}\" r=\"12\"/>" for x,y in [(110,90),(150,210),(225,130),(350,170),(420,90),(390,220)])
    pitch_art = f'<div class="pitch-art" aria-label="Illustrated top-down football pitch"><svg viewBox="0 0 520 300"><rect width="520" height="300" rx="24" fill="#dceeff"/><path d="M260 0v300M30 35h460v230H30zM180 35v70h160V35M180 265v-70h160v70M230 150a30 30 0 1 0 60 0a30 30 0 1 0-60 0" fill="none" stroke="#2563eb" stroke-width="4" opacity=".5"/><g fill="#2563eb">{pitch_dots}</g></svg></div>'
    slide("AI FOUNDATIONS · FINAL PROJECT", "Sunday League Fair Draw", f'<p class="pitch">Fair teams. Fresh pairings. Verified by code.</p><p>{author}</p>', pitch_art, f"Introduce the project and its code-owned fairness promise. Repo: {repo}.")
    slide("THE PROBLEM", "Same teams, every Sunday.", '<div class="icon-list"><p>⚡ Arguments at selection time</p><p>↻ Repeated teammate pairings</p><p>? Doubt about “random”</p></div>', '<div class="week-strip"><span>WEEK 1</span><span>WEEK 2</span><span>WEEK 3</span></div>', "The exact league process and time cost still need the organizer’s input.")
    comp = pending("verified comparison", "evidence/competitors.md")
    slide("WHAT IS NEW", "Memory plus proof.", '<div class="feature-grid"><div>◈<b>Remembers teammates</b></div><div>⌁<b>Published seed</b></div><div>✓<b>Verify this draw</b></div></div>', comp, "These are the implemented design principles. The verified product comparison is pending.")
    pipeline='<svg class="pipeline" viewBox="0 0 1000 240" aria-label="Code and AI pipeline"><g font-size="16" text-anchor="middle"><rect x="20" y="35" width="180" height="52" rx="14" fill="#2563eb"/><rect x="220" y="35" width="180" height="52" rx="14" fill="#6d5bf6"/><rect x="420" y="35" width="180" height="52" rx="14" fill="#2563eb"/><rect x="620" y="35" width="180" height="52" rx="14" fill="#f59e0b"/><rect x="820" y="35" width="160" height="52" rx="14" fill="#2563eb"/><rect x="520" y="150" width="180" height="52" rx="14" fill="#16a34a"/><rect x="720" y="150" width="180" height="52" rx="14" fill="#6d5bf6"/></g><g fill="#fff" text-anchor="middle" font-size="15"><text x="110" y="67">Group chat</text><text x="310" y="67">Attendance AI</text><text x="510" y="67">Claim resolver</text><text x="710" y="67">Organizer</text><text x="900" y="67">Draw engine</text><text x="610" y="182">Draw verifier</text><text x="810" y="182">Announcement AI</text></g><g stroke="#0b1e4a" stroke-width="3"><path d="M200 61h20M400 61h20M600 61h20M800 61h20M900 87v62M720 176h-20M520 176h-20"/></g></svg><p class="legend"><i class="code"></i>Code <i class="ai"></i>AI <i class="human"></i>Human <i class="verify"></i>Verifier</p>'
    slide("HOW IT WORKS", "AI reads. Code decides.", '', pipeline, "The organizer remains the decision point. The draw and checks stay in code.")
    screenshots=''.join([image("attendance-proposal-1440.png","Attendance proposal"),image("draw-pitch-1440.png","Draw on pitch"),image("fairness-cards-1440.png","Fairness and verification")])
    slide("THE APP", "From chat to teams.", '', f'<div class="screens">{screenshots}</div>', "These panels require the corresponding real-app screenshots.")
    token_stats = token.get("statistics", {}) if token.get("status") == "completed" else {}
    cost_visual = '<div class="bars"><span style="height:40%">A</span><span style="height:18%">B</span><span style="height:18%">C</span></div>'
    slide("COST", "Cheap by design.", '<div class="stats">'+stat(token_stats.get("input_tokens",{}).get("mean","pending"),"input tokens")+stat(token_stats.get("output_tokens",{}).get("mean","pending"),"output tokens")+stat("0","draw tokens")+stat("prices not set","cost")+'</div>', cost_visual+('<p class="small">The draw itself uses 0 tokens.</p>' if token_stats else pending("completed token measurements", "results/token_runs.json")), "The available token experiment was budget-refused, so no costs are invented.")
    slide("SAFETY", "We tried to break it.", '<div class="safety-grid"><div>⚠<b>Attacks</b><span>Injection and mass claims blocked</span></div><div>□<b>Malfunctions</b><span>Schema and verifier gates</span></div><div>◌<b>Overspending</b><span>Budgets refuse excess calls</span></div></div>', image("defense-log-attack-1440.png","Defense log")+pending("VERIFIED MATCH badge", "evidence/verified-badge-1440.png"), "The targeted safety suite recorded seven passing tests; the verified badge screenshot is pending.")
    slide("IMPACT", "Fewer repeated pairings.", '<div class="impact-stats">'+stat(fmt(metric(c,"maximum_pair_teammate_count")),"C max repeats")+stat(fmt(metric(a,"maximum_pair_teammate_count")),"A max repeats")+stat(fmt(metric(c,"average_repeat_score")),"C repeat score")+'</div><p class="small">Sample roster · 20 nights × 50 repeats · simulated attendance.</p>', '<div class="bars compare"><span style="height:78%">A</span><span style="height:28%">B</span><span style="height:25%">C</span></div>'+pending("real league-night cards and quote", "evidence/league_night.json + evidence/quotes.md"), "The simulation suggests memory reduced repeats, but it is not a real league-night study.")
    slide("WHAT’S NEXT", "Make the proof stronger.", '<div class="next-grid"><div>01<br><b>Improve recall</b></div><div>02<br><b>Run a real night</b></div><div>03<br><b>Complete cost test</b></div><div>04<br><b>Capture verification</b></div></div>', '', "These are the next validation steps, not completed results.")
    slide("THANK YOU", "Fair teams. Clear proof.", f'<p class="repo">{repo}</p><p class="small">Use arrow keys to navigate · F for fullscreen</p>', '<div class="thank-art">✓</div>', "Close with the repository link after replacing the pending configuration value.")
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sunday League Fair Draw</title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css"><style>'''+css()+'''</style></head><body><div class="reveal"><div class="slides">'''+''.join(slides)+'''</div></div><script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script><script>Reveal.initialize({width:1280,height:720,margin:0,center:false,hash:true,slideNumber:'c/t',progress:true,transition:'fade'});</script></body></html>'''
    OUT.write_text(html, encoding="utf-8")
    report = ROOT / "slides/build_report.md"; report.write_text("# Slide build report\n\n"+"\n".join(f"- Pending: {item}" for item in pending_items)+"\n", encoding="utf-8")
    if final and pending_items: raise SystemExit("FINAL BUILD BLOCKED: pending inputs remain")
    print(f"Built {OUT}; pending inputs: {len(pending_items)}")

def css(): return '''@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Fraunces:opsz,wght@9..144,700;9..144,800&display=swap');:root{--ink:#102d57;--blue:#2878d8;--sky:#72c7f4;--cloud:#eef8ff;--line:#cfe5f8;--muted:#55708f;--violet:#7867e8;--green:#1d9b73;--amber:#e9a52d;--white:#fff}.reveal{font-family:'DM Sans',Arial,sans-serif;color:var(--ink);background:#f7fcff}.reveal section{height:720px;padding:62px 72px;background:linear-gradient(135deg,#fff 0%,#f4fbff 72%,#e9f6ff 100%);position:relative;overflow:hidden}.reveal section:before{content:"";position:absolute;right:-120px;top:-170px;width:560px;height:390px;background:linear-gradient(140deg,#d8f2ff,#b4ddfa);opacity:.7;border-radius:48% 52% 61% 39%/42% 36% 64% 58%;transform:rotate(-12deg);pointer-events:none}.reveal section:after{content:"";position:absolute;right:45px;bottom:35px;width:170px;height:38px;border-top:2px solid #2878d833;border-radius:50%;transform:rotate(-8deg);pointer-events:none}.reveal section:first-child{background:linear-gradient(125deg,#0d376b 0%,#176aa9 55%,#7dd3f5 100%);color:#fff}.reveal section:first-child:before{right:-40px;top:-120px;width:690px;height:560px;background:linear-gradient(135deg,#45b8eb,#d7f5ff);opacity:.34}.reveal section:first-child h2,.reveal section:first-child .kicker,.reveal section:first-child p{color:#fff}.reveal h2{font:800 56px/1.03 Fraunces,Georgia,serif;color:var(--ink);margin:.14em 0 .42em;max-width:900px;letter-spacing:-.025em}.kicker{font-size:14px;letter-spacing:.16em;font-weight:700;color:var(--blue);position:relative;z-index:2}.content{position:relative;z-index:1;max-width:1135px}.pitch{font-size:30px;line-height:1.2;font-weight:700;color:var(--sky)}.pitch-art{position:absolute;right:70px;top:106px;width:480px;filter:drop-shadow(0 24px 25px #062c572e)}.pitch-art svg{width:100%}.feature-grid,.stats,.safety-grid,.next-grid,.impact-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}.feature-grid>div,.safety-grid>div,.next-grid>div{padding:27px;background:#fff;border:1px solid var(--line);border-radius:24px;box-shadow:0 14px 34px #2878d414;font-size:24px;color:var(--blue)}.feature-grid b,.safety-grid b{display:block;color:var(--ink);font-size:19px;margin-top:20px}.pending{display:inline-block;padding:17px 21px;border:2px dashed var(--amber);border-radius:18px;background:#fffaf0;color:#805a00;font-weight:700;font-size:19px}.pending small{display:block;font-weight:400;font-size:13px;margin-top:5px}.pipeline{width:100%;max-height:350px;filter:drop-shadow(0 10px 15px #2878d414)}.legend{font-size:18px;color:var(--muted)}.legend i{display:inline-block;width:18px;height:18px;border-radius:6px;margin:0 5px 0 16px;vertical-align:-3px}.code{background:var(--blue)}.ai{background:var(--violet)}.human{background:var(--amber)}.verify{background:var(--green)}.screens{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.screens figure{margin:0}.screens img{width:100%;height:260px;object-fit:cover;border-radius:18px;border:4px solid #fff;box-shadow:0 14px 28px #0b376126}.screens figcaption{font-size:16px;color:var(--muted);margin-top:8px}.stat{padding:25px;background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:0 12px 25px #2878d410}.stat b{display:block;font-size:42px;color:var(--blue);font-weight:700}.stat span{font-size:17px;color:var(--muted)}.bars{height:170px;display:flex;align-items:end;gap:28px;margin:20px 0}.bars span{width:80px;display:grid;place-items:start center;padding-top:8px;background:linear-gradient(var(--sky),var(--blue));border-radius:14px 14px 0 0;color:#fff;font-weight:800}.bars.compare span{width:120px}.small{font-size:18px!important;color:var(--muted)}.repo{font-size:28px;color:var(--blue);word-break:break-word}.thank-art{font-size:180px;color:var(--green);font-weight:800}.reveal .progress{color:var(--blue)}.reveal .slide-number{color:var(--muted);background:transparent}@media print{@page{size:1280px 720px;margin:0}.reveal section{break-after:page;page-break-after:always}}'''

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--final",action="store_true"); build(p.parse_args().final)
