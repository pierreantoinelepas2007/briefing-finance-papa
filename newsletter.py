#!/usr/bin/env python3
"""
Finance Newsletter — Morning Market Brief professionnel
Intègre : FRED (taux, spreads), CNN Fear & Greed, RSS multi-sources
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

# ─── Flux RSS par catégorie ────────────────────────────────────────────────────

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

# ─── FRED API — Données macro en temps réel ────────────────────────────────────

def fetch_fred_series(series_id, api_key, limit=1):
    """Récupère la dernière valeur d'une série FRED."""
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}"
            f"&sort_order=desc&limit={limit}&file_type=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        obs = data.get("observations", [])
        if obs:
            return obs[0].get("value", "N/A"), obs[0].get("date", "")
    except Exception as e:
        print(f"  ⚠️  FRED ({series_id}): {e}")
    return "N/A", ""

def fetch_macro_dashboard():
    """Récupère les indicateurs macro clés depuis FRED."""
    api_key = CONFIG.get("FRED_API_KEY", "")
    if not api_key:
        return None

    print("  → Récupération données FRED...")
    indicators = {}

    # Taux 10 ans US
    val, date = fetch_fred_series("DGS10", api_key)
    indicators["US 10Y Yield"] = {"value": f"{val}%", "date": date, "desc": "Taux obligation US 10 ans"}

    # Taux 2 ans US
    val2, _ = fetch_fred_series("DGS2", api_key)
    indicators["US 2Y Yield"] = {"value": f"{val2}%", "date": date, "desc": "Taux obligation US 2 ans"}

    # Spread 10Y-2Y (courbe des taux)
    try:
        spread = round(float(val) - float(val2), 2)
        sign = "+" if spread >= 0 else ""
        indicators["Spread 10Y-2Y"] = {
            "value": f"{sign}{spread} bps",
            "date": date,
            "desc": "Courbe des taux — positif = normale, négatif = inversée"
        }
    except:
        pass

    # Fed Funds Rate
    val, date = fetch_fred_series("FEDFUNDS", api_key)
    indicators["Fed Funds Rate"] = {"value": f"{val}%", "date": date, "desc": "Taux directeur Fed"}

    # Taux BCE (shadow rate approximation via ECBESTRVOLWGT)
    val, date = fetch_fred_series("ECBESTRVOLWGT", api_key)
    indicators["€STR (BCE)"] = {"value": f"{val}%", "date": date, "desc": "Taux au jour le jour zone euro"}

    # Inflation US CPI YoY
    val, date = fetch_fred_series("CPIAUCSL", api_key)
    indicators["CPI US"] = {"value": val, "date": date, "desc": "Indice prix consommation US (niveau)"}

    # Taux chômage US
    val, date = fetch_fred_series("UNRATE", api_key)
    indicators["Chômage US"] = {"value": f"{val}%", "date": date, "desc": "Taux de chômage américain"}

    return indicators

# ─── CNN Fear & Greed Index ────────────────────────────────────────────────────

def fetch_fear_greed():
    """Récupère le CNN Fear & Greed Index."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://edition.cnn.com/"
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        score = data["fear_and_greed"]["score"]
        rating = data["fear_and_greed"]["rating"]
        score = round(float(score))
        labels = {
            "extreme fear": "Peur Extrême 😨",
            "fear": "Peur 😟",
            "neutral": "Neutre 😐",
            "greed": "Avidité 🤑",
            "extreme greed": "Avidité Extrême 🚀",
        }
        label = labels.get(rating.lower(), rating)
        return score, label
    except Exception as e:
        print(f"  ⚠️  Fear & Greed: {e}")
        return None, None

# ─── Récupération des articles RSS ────────────────────────────────────────────

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
                    articles.append({
                        "title": title,
                        "summary": summary[:600],
                        "source": source,
                    })
        except Exception as e:
            print(f"  ⚠️  RSS ({url}): {e}")

    return articles

# ─── Résumé IA avec Groq ───────────────────────────────────────────────────────

def summarize_with_groq(category, articles):
    if not articles:
        return "<p style='color:#888;font-style:italic;'>Aucun article disponible aujourd'hui.</p>"

    client = Groq(api_key=CONFIG["GROQ_API_KEY"])

    articles_text = "\n".join(
        f"[{a['source']}] {a['title']}: {a['summary']}" for a in articles[:10]
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """Tu es un analyste financier senior francophone, 20 ans d'expérience en marchés financiers, macroéconomie et gestion d'actifs.
Tu rédiges des briefings pour un professionnel expert de la finance.
Style : précis, technique, dense. Vocabulaire exact : spreads, yields, bps, P/E, QE, forward guidance, hawkish/dovish, risk-off/risk-on, tapering, etc.
Tu analyses causes ET conséquences. Tu fais des liens entre événements macro et réactions de marché.
Pas de vulgarisation — ton lecteur est expert."""
            },
            {
                "role": "user",
                "content": f"""Dépêches du jour — {category}

{articles_text}

Format strict :

• [Fait — précis, chiffres si disponibles]
  → Analyse : [2-3 phrases : causes, mécanismes de transmission, implications marchés/portefeuilles. Vocabulaire financier approprié.]

3 à 5 points. Priorise les faits les plus market-moving. Dense, sans remplissage."""
            }
        ],
        max_tokens=900,
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()

# ─── Formatage HTML ────────────────────────────────────────────────────────────

def format_summary_html(summary):
    html = ""
    lines = summary.split("\n")
    in_block = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_block:
                html += "</div>"
                in_block = False
            continue
        if line.startswith("•"):
            if in_block:
                html += "</div>"
            text = line.lstrip("•").strip()
            html += f"""<div style="margin-bottom:20px;">
              <p style="margin:0 0 8px;font-size:15px;color:#0d1b2a;font-weight:700;line-height:1.5;">• {text}</p>"""
            in_block = True
        elif line.startswith("→"):
            text = line.lstrip("→").replace("Analyse :", "").strip()
            html += f"""<p style="margin:0 0 0 16px;font-size:13.5px;color:#444;line-height:1.8;
                         border-left:3px solid #c9a84c;padding:6px 0 6px 14px;background:#fdfbf5;">
                <span style="color:#b8962e;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Analyse</span><br>
                {text}</p>"""
        else:
            html += f'<p style="margin:4px 0 4px 16px;font-size:14px;color:#555;">{line}</p>'

    if in_block:
        html += "</div>"
    return html or f'<p style="color:#888;">{summary}</p>'


def build_macro_dashboard_html(indicators, fear_score, fear_label):
    """Construit le bloc dashboard macro en haut de l'email."""
    if not indicators and fear_score is None:
        return ""

    cells = ""

    # Indicateurs FRED
    if indicators:
        for name, data in indicators.items():
            val = data["value"]
            # Couleur selon le type d'indicateur
            if "Spread" in name:
                try:
                    num = float(val.replace("+","").replace(" bps",""))
                    color = "#1a6b3c" if num >= 0 else "#c0392b"
                except:
                    color = "#0d1b2a"
            elif "Chômage" in name or "CPI" in name:
                color = "#0d1b2a"
            else:
                color = "#1a4a6b"

            cells += f"""
            <td style="padding:12px 16px;text-align:center;border-right:1px solid #1e3050;">
              <p style="margin:0;font-size:10px;color:#6a8aaa;letter-spacing:1.5px;text-transform:uppercase;">{name}</p>
              <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:{color};font-family:'Georgia',serif;">{val}</p>
              <p style="margin:2px 0 0;font-size:10px;color:#4a6080;">{data['date']}</p>
            </td>"""

    # Fear & Greed
    if fear_score is not None:
        if fear_score <= 25:
            fg_color = "#c0392b"
        elif fear_score <= 45:
            fg_color = "#e67e22"
        elif fear_score <= 55:
            fg_color = "#7f8c8d"
        elif fear_score <= 75:
            fg_color = "#27ae60"
        else:
            fg_color = "#1a6b3c"

        cells += f"""
        <td style="padding:12px 16px;text-align:center;">
          <p style="margin:0;font-size:10px;color:#6a8aaa;letter-spacing:1.5px;text-transform:uppercase;">Fear & Greed</p>
          <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:{fg_color};font-family:'Georgia',serif;">{fear_score}/100</p>
          <p style="margin:2px 0 0;font-size:10px;color:#4a6080;">{fear_label}</p>
        </td>"""

    if not cells:
        return ""

    return f"""
    <tr>
      <td style="background:#0d1b2a;padding:0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1e3050;">
          <tr>{cells}</tr>
        </table>
      </td>
    </tr>"""


def build_email_html(summaries, indicators, fear_score, fear_label):
    today = datetime.now().strftime("%A %d %B %Y").capitalize()
    now   = datetime.now().strftime("%H:%M")

    category_colors = {
        "📈 Marchés boursiers":                        "#1a5c38",
        "🌍 Économie mondiale & Politique monétaire":  "#1a3d6b",
        "₿ Crypto / Actifs numériques":                "#92400e",
        "🏠 Immobilier, Taux & Crédit":                "#5b1a4a",
        "🛢️ Matières premières & Énergie":             "#3d2e0f",
    }

    sections_html = ""
    for category, summary in summaries.items():
        color = category_colors.get(category, "#333")
        content_html = format_summary_html(summary)
        sections_html += f"""
        <div style="margin-bottom:40px;">
          <div style="border-left:4px solid {color};padding-left:18px;margin-bottom:16px;">
            <h2 style="margin:0;font-size:12px;color:{color};font-family:'Georgia',serif;
                        text-transform:uppercase;letter-spacing:2.5px;font-weight:700;">{category}</h2>
          </div>
          <div style="padding-left:4px;">{content_html}</div>
          <div style="border-bottom:1px solid #f0ede6;margin-top:32px;"></div>
        </div>"""

    dashboard_html = build_macro_dashboard_html(indicators, fear_score, fear_label)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#eceae3;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#eceae3;padding:48px 0;">
    <tr><td align="center">
      <table width="680" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:4px;overflow:hidden;box-shadow:0 2px 30px rgba(0,0,0,0.12);">

        <!-- HEADER -->
        <tr>
          <td style="background:#0a1628;padding:44px 48px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <p style="margin:0;color:#c9a84c;font-size:10px;letter-spacing:5px;text-transform:uppercase;font-family:'Georgia',serif;">
                    Briefing Financier Quotidien
                  </p>
                  <h1 style="margin:10px 0 0;color:#fff;font-size:26px;font-family:'Georgia',serif;font-weight:400;">
                    Morning Market Brief
                  </h1>
                </td>
                <td align="right" style="vertical-align:bottom;">
                  <p style="margin:0;color:#c9a84c;font-size:24px;font-family:'Georgia',serif;">{datetime.now().strftime("%d.%m")}</p>
                  <p style="margin:2px 0 0;color:#4a6080;font-size:11px;">{now} CET</p>
                </td>
              </tr>
            </table>
            <p style="margin:16px 0 0;color:#4a6080;font-size:12px;border-top:1px solid #1e3050;padding-top:14px;">{today}</p>
          </td>
        </tr>

        <!-- DASHBOARD MACRO -->
        {dashboard_html}

        <!-- CONTENU -->
        <tr>
          <td style="padding:40px 48px 8px;">{sections_html}</td>
        </tr>

        <!-- SOURCES -->
        <tr>
          <td style="padding:0 48px 28px;">
            <p style="margin:0;font-size:11px;color:#bbb;letter-spacing:0.5px;">
              SOURCES — Reuters · Les Échos · Le Monde · The Economist · MarketWatch · Zonebourse · Peterson Institute · CoinTelegraph · MoneVox · OilPrice · FRED · CNN F&G
            </p>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f7f5f0;padding:20px 48px;border-top:1px solid #e8e4dc;">
            <p style="margin:0;color:#bbb;font-size:11px;line-height:1.7;">
              Ce briefing est généré automatiquement. Il ne constitue pas un conseil en investissement.<br>
              <em>Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}</em>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

# ─── Envoi de l'email ──────────────────────────────────────────────────────────

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

# ─── Programme principal ───────────────────────────────────────────────────────

def main():
    print(f"\n📊 Morning Brief — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)

    # Dashboard macro
    print("\n📡 Données macro temps réel")
    indicators = fetch_macro_dashboard()
    print("  → Fear & Greed Index...")
    fear_score, fear_label = fetch_fear_greed()
    if fear_score:
        print(f"  ✓ Fear & Greed : {fear_score}/100 — {fear_label}")

    # Résumés par catégorie
    summaries = {}
    for category, feeds in RSS_FEEDS.items():
        print(f"\n{category}")
        articles = fetch_articles(feeds)
        print(f"  → {len(articles)} articles trouvés")
        summaries[category] = summarize_with_groq(category, articles)
        print(f"  ✓ Analyse générée")

    print("\n📧 Envoi du briefing...")
    html = build_email_html(summaries, indicators, fear_score, fear_label)
    send_email(html)
    print("\n✅ Morning Brief envoyé avec succès !\n")

if __name__ == "__main__":
    main()
