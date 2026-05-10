"""Pure parser tests for the summerhouse scrape helper."""

from app.services.scrape import parse_summerhouse_html


def test_prefers_open_graph_metadata():
    html = """
    <html><head>
      <meta property="og:title" content="Min Hytte" />
      <meta property="og:description" content="En dejlig lille hytte." />
      <meta property="og:image" content="https://cdn.example.com/h.jpg" />
      <title>Backup title</title>
    </head><body><h1>Heading</h1></body></html>
    """
    s = parse_summerhouse_html(html, "https://example.com/page")
    assert s.title == "Min Hytte"
    assert s.summary == "En dejlig lille hytte."
    assert s.image_url == "https://cdn.example.com/h.jpg"


def test_falls_back_to_h1_and_first_long_paragraph():
    html = """
    <html><head><title>T</title></head>
    <body>
      <h1>Skagen Hus</h1>
      <p>kort</p>
      <p>Et virkelig dejligt og hyggeligt sommerhus med plads til hele familien.</p>
      <img src="/img/hero.png" />
    </body></html>
    """
    s = parse_summerhouse_html(html, "https://example.com/houses/42")
    assert s.title == "Skagen Hus"
    assert s.summary is not None and "hyggeligt" in s.summary
    assert s.image_url == "https://example.com/img/hero.png"


def test_summary_is_clipped():
    long_text = "A" * 1000
    html = f"<html><body><p>{long_text}</p></body></html>"
    s = parse_summerhouse_html(html, "https://example.com")
    assert s.summary is not None
    assert len(s.summary) <= 600


def test_skips_generic_newsletter_meta_description():
    html = """
    <html><head>
      <meta property="og:title" content="Bjerregård" />
      <meta property="og:description" content="Tilmeld dig vores nyhedsbrev og modtag eksklusive tilbud." />
    </head><body>
      <p>Hyggeligt sommerhus med plads til ti personer, spabad og kort til stranden.</p>
    </body></html>
    """
    s = parse_summerhouse_html(html, "https://example.com")
    assert s.summary is not None
    assert "Hyggeligt sommerhus" in s.summary
    assert "nyhedsbrev" not in s.summary.lower()


def test_keeps_specific_meta_description_when_present():
    html = """
    <html><head>
      <meta property="og:description" content="6 sovepladser, sauna og udsigt til vandet i et roligt sommerhusomraade." />
    </head><body>
      <p>Tilmeld dig vores nyhedsbrev og modtag eksklusive tilbud.</p>
    </body></html>
    """
    s = parse_summerhouse_html(html, "https://example.com")
    assert s.summary is not None
    assert "sovepladser" in s.summary
