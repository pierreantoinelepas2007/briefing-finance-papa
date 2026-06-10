#!/usr/bin/env python3
"""
Finance Newsletter — Morning Market Brief professionnel
Style : Financial Times — classique, crème, trait rouge
"""

import feedparser
import smtplib
import urllib.request
import json
from groq import Groq
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import CONFIG

# ─── Flux RSS ─────────────────────────────────────────────────────────────────

RSS_FEEDS = {
    "📈 Marchés boursiers": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://finance.yahoo.com/rss/topstories",
        "https://www.lemonde.fr/economie/rss_full.xml",
        "https://www.lesechos.fr/rss/rss_finance-marches.xml",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.zonebourse.com/rss/actualites.xml",
    ],
    "🌍 Économie mondiale & Politique monétaire": [
        "https://www.economist.com/finance-and-economics/rss.xml",
        "https://feeds.reuters.com/reuters/UKdomesticNews",
        "https://www.lesechos.fr/rss/rss_une.xml",
        "https://www.lemonde.fr/economie/rss_full.xml",
        "https://www.piie.com/rss.xml",
    ],
    "₿ Crypto / Actifs numériques": [
        "https://cointelegraph.com/rss",
        "https://cryptonews.com/news/feed/",
    ],
    "🏠 Immobilier, Taux & Crédit": [
        "https://www.moneyvox.fr/flux/rss.php",
        "https://www.lesechos.fr/rss/rss_finance-marches.xml",
        "https://feeds.reuters.com/reuters/businessNews",
    ],
    "🛢️ Matières premières & Énergie": [
        "https://feeds.reuters.com/reuters/commoditiesNews",
        "https://oilprice.com/rss/main",
        "https://www.lemonde.fr/economie/rss_full.xml",
    ],
}

# ─── Fear & Greed ─────────────────────────────────────────────────────────────

def fetch_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed"
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        score  = round(float(data["fear_and_greed"]["score"]))
        rating = data["fear_and_greed"]["rating"].lower()
        labels = {
            "extreme fear": "Peur Extrême",
            "fear":         "Peur",
            "neutral":      "Neutre",
            "greed":        "Avidité",
            "extreme greed":"Avidité Extrême",
        }
        return score, labels.get(rating, rating)
    except Exception as e:
        print(f"  ⚠️  Fear & Greed: {e}")
        return None, None

# ─── Récupération articles RSS ────────────────────────────────────────────────

def fetch_articles(feeds, max_per_feed=6):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    import calendar
                    published = datetime.fromtimestamp(
                        calendar.timegm(entry.published_parsed), tz=timezone.utc
                    )
                if published and published < cutoff:
                    continue
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                source  = feed.feed.get("title", url)
                if title:
                    articles.append({"title": title, "summary": summary[:600], "source": source})
        except Exception as e:
            print(f"  ⚠️  RSS ({url}): {e}")
    return articles

# ─── Résumé IA Groq ───────────────────────────────────────────────────────────

def summarize_with_groq(category, articles):
    if not articles:
        return []

    client = Groq(api_key=CONFIG["GROQ_API_KEY"])
    articles_text = "\n".join(
        f"[{a['source']}] {a['title']}: {a['summary']}" for a in articles[:10]
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """Tu es un analyste financier senior francophone, 20 ans d'expérience.
Tu rédiges pour un professionnel expert de la finance.
Style : précis, technique, dense. Vocabulaire exact : spreads, yields, bps, P/E, QE, forward guidance, hawkish/dovish, risk-off/risk-on, tapering, duration risk, etc.
Tu analyses causes ET conséquences. Tu fais des liens entre événements macro et réactions de marché."""
            },
            {
                "role": "user",
                "content": f"""Dépêches du jour — {category}

{articles_text}

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après, avec ce format exact :
[
  {{"fait": "titre court et factuel avec chiffres", "analyse": "2-3 phrases d'analyse technique avec vocabulaire financier"}},
  {{"fait": "...", "analyse": "..."}}
]

3 à 5 objets maximum. Priorise les faits les plus market-moving."""
            }
        ],
        max_tokens=1000,
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()
    try:
        raw = raw[raw.find("["):raw.rfind("]")+1]
        return json.loads(raw)
    except:
        return [{"fait": "Résumé du jour", "analyse": raw}]

# ─── Construction email HTML — Style FT ───────────────────────────────────────

def build_email_html(summaries, fear_score, fear_label):
    today = datetime.now().strftime("%A %d %B %Y").capitalize()
    now   = datetime.now().strftime("%H:%M")

    category_colors = {
        "📈 Marchés boursiers":                        "#b30000",
        "🌍 Économie mondiale & Politique monétaire":  "#b30000",
        "₿ Crypto / Actifs numériques":                "#b30000",
        "🏠 Immobilier, Taux & Crédit":                "#b30000",
        "🛢️ Matières premières & Énergie":             "#b30000",
    }

    # Dashboard Fear & Greed
    if fear_score is not None:
        if fear_score <= 25:   fg_color = "#c0392b"
        elif fear_score <= 45: fg_color = "#e67e22"
        elif fear_score <= 55: fg_color = "#888"
        elif fear_score <= 75: fg_color = "#27ae60"
        else:                  fg_color = "#1a6b3c"
        fear_html = f"""
        <td width="25%" style="padding:14px 18px;background:#fff3e8;border-radius:6px;">
          <p style="margin:0;font-size:9px;color:#999;text-transform:uppercase;letter-spacing:1px;font-family:Arial,sans-serif;">Fear &amp; Greed</p>
          <p style="margin:4px 0 0;font-size:20px;font-weight:700;color:{fg_color};font-family:Georgia,serif;">{fear_score}</p>
          <p style="margin:2px 0 0;font-size:11px;color:{fg_color};font-family:Arial,sans-serif;">{fear_label}</p>
        </td>"""
    else:
        fear_html = ""

    # Sections
    sections_html = ""
    for category, points in summaries.items():
        if not points:
            continue
        label = category.split(" ", 1)[1] if " " in category else category
        items_html = ""
        for p in points:
            items_html += f"""
            <tr>
              <td style="padding:0 0 18px 0;">
                <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#111111;font-family:Georgia,serif;line-height:1.5;">
                  &bull; {p.get('fait','')}
                </p>
                <p style="margin:0 0 0 14px;font-size:13px;color:#555555;line-height:1.8;font-family:Georgia,serif;border-left:2px solid #e8d5b0;padding-left:12px;">
                  {p.get('analyse','')}
                </p>
              </td>
            </tr>"""

        sections_html += f"""
        <tr>
          <td style="padding:0 0 28px 0;">
            <p style="margin:0 0 14px;font-size:10px;color:#b30000;text-transform:uppercase;
                       letter-spacing:2px;font-weight:700;font-family:Arial,sans-serif;
                       border-bottom:1px solid #f0e0c8;padding-bottom:8px;">
              {label}
            </p>
            <table width="100%" cellpadding="0" cellspacing="0">
              {items_html}
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f2ede4;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2ede4;padding:40px 0;">
  <tr><td align="center">
  <table width="640" cellpadding="0" cellspacing="0"
         style="background:#fffdf8;border-radius:4px;overflow:hidden;border:1px solid #e8d5b0;">

    <!-- HEADER -->
    <tr>
      <td style="background:#ffffff;padding:28px 36px 20px;border-bottom:3px solid #cc2200;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <p style="margin:0;font-size:22px;font-weight:400;color:#111;font-family:Georgia,serif;letter-spacing:0.3px;">
                Finance &amp; Marchés
              </p>
              <p style="margin:6px 0 0;font-size:11px;color:#999;font-family:Arial,sans-serif;letter-spacing:0.5px;">
                {today} &nbsp;·&nbsp; {now} CET
              </p>
            </td>
            <td align="right" style="vertical-align:middle;">
              <span style="background:#cc2200;color:#ffffff;padding:5px 14px;font-size:11px;
                            font-family:Arial,sans-serif;font-weight:700;letter-spacing:1px;
                            text-transform:uppercase;border-radius:3px;">
                DAILY
              </span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- DASHBOARD -->
    <tr>
      <td style="background:#ffffff;padding:16px 36px 20px;border-bottom:1px solid #e8d5b0;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr style="gap:12px;">
            {fear_html}
          </tr>
        </table>
      </td>
    </tr>

    <!-- CONTENU -->
    <tr>
      <td style="padding:28px 36px 8px;background:#fffdf8;">
        <table width="100%" cellpadding="0" cellspacing="0">
          {sections_html}
        </table>
      </td>
    </tr>

    <!-- SOURCES -->
    <tr>
      <td style="padding:0 36px 20px;background:#fffdf8;">
        <p style="margin:0;font-size:10px;color:#bbb;font-family:Arial,sans-serif;letter-spacing:0.3px;">
          Sources &mdash; Reuters &middot; Les &Eacute;chos &middot; Le Monde &middot; The Economist &middot; MarketWatch &middot; Zonebourse &middot; Peterson Institute &middot; CoinTelegraph &middot; MoneVox &middot; OilPrice &middot; CNN F&amp;G
        </p>
      </td>
    </tr>

    <!-- FOOTER -->
    <tr>
      <td style="background:#f7f3ec;padding:18px 36px;border-top:1px solid #e8d5b0;">
        <p style="margin:0;color:#bbb;font-size:11px;font-family:Arial,sans-serif;line-height:1.6;">
          Ce briefing est g&eacute;n&eacute;r&eacute; automatiquement &agrave; des fins d'information.
          Il ne constitue pas un conseil en investissement.
          &mdash; <em>G&eacute;n&eacute;r&eacute; le {datetime.now().strftime("%d/%m/%Y &agrave; %H:%M")}</em>
        </p>
      </td>
    </tr>

  </table>
  </td></tr>
</table>
</body>
</html>"""

# ─── Envoi email ──────────────────────────────────────────────────────────────

def send_email(html_content):
    today = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Morning Brief — {today}"
    msg["From"]    = CONFIG["SENDER_EMAIL"]
    msg["To"]      = CONFIG["RECIPIENT_EMAIL"]
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(CONFIG["SENDER_EMAIL"], CONFIG["GMAIL_APP_PASSWORD"])
        server.sendmail(CONFIG["SENDER_EMAIL"], CONFIG["RECIPIENT_EMAIL"], msg.as_string())
    print(f"✅ Email envoyé à {CONFIG['RECIPIENT_EMAIL']}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n📊 Morning Brief — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)

    print("\n📡 Fear & Greed Index...")
    fear_score, fear_label = fetch_fear_greed()
    if fear_score:
        print(f"  ✓ {fear_score}/100 — {fear_label}")

    summaries = {}
    for category, feeds in RSS_FEEDS.items():
        print(f"\n{category}")
        articles = fetch_articles(feeds)
        print(f"  → {len(articles)} articles trouvés")
        summaries[category] = summarize_with_groq(category, articles)
        print(f"  ✓ Analyse générée")

    print("\n📧 Envoi du briefing...")
    html = build_email_html(summaries, fear_score, fear_label)
    send_email(html)
    print("\n✅ Morning Brief envoyé !\n")

if __name__ == "__main__":
    main()
