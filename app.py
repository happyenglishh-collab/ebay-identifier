import streamlit as st
import anthropic
import base64
import json
import re

st.set_page_config(
    page_title="eBay Item Identifier",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { padding: 0.5rem 0.75rem 1rem; max-width: 100%; }
  h1 { font-size: 1.5rem !important; }
  h2 { font-size: 1.15rem !important; }
  h3 { font-size: 1rem !important; }
  .stButton > button { width: 100%; border-radius: 8px; font-weight: 600; }
  .era-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }
  .era-antique  { background: #1a3a1a; color: #39FF14; border: 1px solid #39FF14; }
  .era-vintage  { background: #1a2a3a; color: #00BFFF; border: 1px solid #00BFFF; }
  .era-modern   { background: #2a2a2a; color: #AAAAAA; border: 1px solid #555; }
  .price-box {
    background: #1C1F26;
    border: 1px solid #FFEB3B;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 10px 0;
    text-align: center;
  }
  .price-label { font-size: 0.7rem; color: #AAAAAA; letter-spacing: 1px; text-transform: uppercase; }
  .price-value { font-size: 1.6rem; font-weight: 800; color: #FFEB3B; }
  .section-header {
    font-size: 0.7rem;
    color: #00BFFF;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    font-weight: 700;
    margin: 14px 0 6px;
    border-bottom: 1px solid #1C1F26;
    padding-bottom: 4px;
  }
  .tag {
    display: inline-block;
    background: #1C1F26;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 0.75rem;
    margin: 2px 3px 2px 0;
    color: #FAFAFA;
  }
  .keyword-tag {
    border-color: #00BFFF44;
    color: #00BFFF;
    background: #0a1520;
  }
  .tip-row {
    background: #1C1F26;
    border-left: 3px solid #39FF14;
    border-radius: 0 6px 6px 0;
    padding: 7px 10px;
    margin: 5px 0;
    font-size: 0.82rem;
  }
  .color-swatch {
    display: inline-block;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    margin-right: 5px;
    border: 2px solid #333;
    vertical-align: middle;
  }
  .item-title {
    font-size: 1.3rem;
    font-weight: 800;
    color: #FAFAFA;
    margin: 8px 0 4px;
    line-height: 1.3;
  }
  .category-text {
    font-size: 0.8rem;
    color: #AAAAAA;
    margin-bottom: 8px;
  }
  .stCameraInput > div > div { border-radius: 10px; }
  .warning-box {
    background: #2a1a00;
    border: 1px solid #FFEB3B44;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.8rem;
    color: #CCAA55;
  }
</style>
""", unsafe_allow_html=True)

ANALYZE_PROMPT = """You are an expert antique dealer, vintage item appraiser, and eBay power seller with 20+ years of experience.
Analyze this item photo and provide a detailed assessment for eBay resale.

Return ONLY a valid JSON object with exactly these fields (no markdown, no explanation):

{
  "item_name": "Specific descriptive name of the item",
  "category": "eBay category (e.g. Pottery & Glass, Collectibles, Clothing, Electronics, etc.)",
  "era": "antique" or "vintage" or "modern",
  "era_note": "antique = 100+ years old, vintage = 20-100 years old, modern = less than 20 years old",
  "estimated_period": "e.g. 1920s-1940s or Victorian Era or 1990s",
  "brand_or_maker": "Brand, maker, or manufacturer if visible or identifiable, else null",
  "model_name": "Specific model, pattern, or line name (critical for flatware e.g. 'Oneida Community Silverplate Paul Revere', pottery marks, china patterns, vintage electronics models, etc.), else null",
  "materials": ["list", "of", "materials"],
  "dominant_colors": ["color1", "color2"],
  "color_hex": ["#hex1", "#hex2"],
  "condition": "Excellent" or "Very Good" or "Good" or "Fair" or "Poor",
  "condition_notes": "Brief description of visible condition issues or highlights",
  "ebay_price_low": 5,
  "ebay_price_high": 45,
  "listing_title": "Suggested eBay listing title (max 80 chars, keyword-rich)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7", "keyword8"],
  "selling_tips": ["tip1", "tip2", "tip3"],
  "notable_features": ["feature1", "feature2"],
  "authenticity_markers": "What to check to verify authenticity or age, or null if not applicable",
  "confidence": "high" or "medium" or "low"
}

Rules:
- model_name is ESPECIALLY important for flatware, silverware, china, pottery, and vintage electronics — look for pattern names, hallmarks, or maker's marks (e.g., "Wm. Rogers Extra Plate - Flair", "Reed & Barton Dimension Sterling", "Gorham Chantilly")
- era must be exactly one of: antique, vintage, modern
- ebay_price_low and ebay_price_high must be numbers (USD), realistic for Goodwill resale
- listing_title should include era, material, color, and use when applicable
- keywords should be actual eBay search terms buyers would use
- selling_tips should be actionable advice (photography angles, timing, bundling, etc.)
- If you cannot identify the item clearly, set confidence to "low" and still fill all fields with best guesses
- color_hex should have the same length as dominant_colors"""


def encode_image(image_bytes: bytes, mime_type: str) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def analyze_image(image_bytes: bytes, mime_type: str) -> dict:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    b64 = encode_image(image_bytes, mime_type)

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1500,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": ANALYZE_PROMPT},
                ],
            }
        ],
    )

    raw = ""
    for block in response.content:
        if block.type == "text":
            raw = block.text
            break

    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        return json.loads(json_match.group())
    raise ValueError(f"Could not parse JSON from response: {raw[:300]}")


def era_badge(era: str) -> str:
    label = {"antique": "ANTIQUE (100+ yrs)", "vintage": "VINTAGE (20-100 yrs)", "modern": "MODERN"}.get(era.lower(), era.upper())
    css_class = f"era-{era.lower()}"
    return f'<span class="era-badge {css_class}">{label}</span>'


def render_results(data: dict):
    st.markdown(f'<div class="item-title">{data.get("item_name", "Unknown Item")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="category-text">{data.get("category", "")}</div>', unsafe_allow_html=True)

    era = data.get("era", "modern").lower()
    period = data.get("estimated_period", "")
    confidence = data.get("confidence", "medium")
    conf_icon = {"high": "●", "medium": "◐", "low": "○"}.get(confidence, "◐")
    conf_color = {"high": "#39FF14", "medium": "#FFEB3B", "low": "#FF6B6B"}.get(confidence, "#FFEB3B")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(era_badge(era), unsafe_allow_html=True)
        if period:
            st.markdown(f'<span style="font-size:0.78rem;color:#888;margin-left:8px;">{period}</span>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<span style="font-size:0.75rem;color:{conf_color};float:right;">{conf_icon} {confidence.title()} confidence</span>', unsafe_allow_html=True)

    price_low = data.get("ebay_price_low", 0)
    price_high = data.get("ebay_price_high", 0)
    st.markdown(f"""
    <div class="price-box">
      <div class="price-label">Estimated eBay Price Range</div>
      <div class="price-value">${price_low} – ${price_high}</div>
    </div>
    """, unsafe_allow_html=True)

    brand = data.get("brand_or_maker")
    model_name = data.get("model_name")
    condition = data.get("condition", "")
    condition_notes = data.get("condition_notes", "")

    if brand or model_name:
        st.markdown('<div class="section-header">Brand & Model</div>', unsafe_allow_html=True)
        if brand:
            st.markdown(f'<span style="font-size:0.88rem;color:#FFEB3B;font-weight:700;">🏷 {brand}</span>', unsafe_allow_html=True)
        if model_name:
            st.markdown(f'<span style="font-size:0.85rem;color:#FAFAFA;">Pattern / Model: <strong>{model_name}</strong></span>', unsafe_allow_html=True)

    if condition:
        st.markdown('<div class="section-header">Condition</div>', unsafe_allow_html=True)
        cond_color = {"Excellent": "#39FF14", "Very Good": "#7FFF00", "Good": "#FFEB3B", "Fair": "#FFA500", "Poor": "#FF6B6B"}.get(condition, "#FAFAFA")
        st.markdown(f'<span style="font-size:0.95rem;font-weight:700;color:{cond_color};">{condition}</span>', unsafe_allow_html=True)
        if condition_notes:
            st.markdown(f'<div style="font-size:0.78rem;color:#AAAAAA;margin-top:3px;">{condition_notes}</div>', unsafe_allow_html=True)

    materials = data.get("materials", [])
    if materials:
        st.markdown('<div class="section-header">Materials</div>', unsafe_allow_html=True)
        tags = "".join(f'<span class="tag">{m}</span>' for m in materials)
        st.markdown(tags, unsafe_allow_html=True)

    colors = data.get("dominant_colors", [])
    hexes = data.get("color_hex", [])
    if colors:
        st.markdown('<div class="section-header">Dominant Colors</div>', unsafe_allow_html=True)
        color_html = ""
        for i, c in enumerate(colors):
            hex_val = hexes[i] if i < len(hexes) else "#888888"
            color_html += f'<span class="color-swatch" style="background:{hex_val};"></span><span style="font-size:0.82rem;margin-right:12px;">{c}</span>'
        st.markdown(color_html, unsafe_allow_html=True)

    features = data.get("notable_features", [])
    if features:
        st.markdown('<div class="section-header">Notable Features</div>', unsafe_allow_html=True)
        for f in features:
            st.markdown(f'<span class="tag">✦ {f}</span>', unsafe_allow_html=True)

    listing_title = data.get("listing_title", "")
    if listing_title:
        st.markdown('<div class="section-header">Suggested eBay Title</div>', unsafe_allow_html=True)
        st.code(listing_title, language=None)

    keywords = data.get("keywords", [])
    if keywords:
        st.markdown('<div class="section-header">eBay Search Keywords</div>', unsafe_allow_html=True)
        kw_html = "".join(f'<span class="tag keyword-tag">{k}</span>' for k in keywords)
        st.markdown(kw_html, unsafe_allow_html=True)

    tips = data.get("selling_tips", [])
    if tips:
        st.markdown('<div class="section-header">Selling Tips</div>', unsafe_allow_html=True)
        for tip in tips:
            st.markdown(f'<div class="tip-row">💡 {tip}</div>', unsafe_allow_html=True)

    auth = data.get("authenticity_markers")
    if auth:
        st.markdown('<div class="section-header">Authenticity / Age Markers</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="warning-box">🔎 {auth}</div>', unsafe_allow_html=True)


def main():
    st.markdown(
        '<h1 style="margin-bottom:0;">🔍 <span style="color:#FFEB3B;">eBay</span> <span style="color:#00BFFF;">Item</span> Identifier</h1>',
        unsafe_allow_html=True,
    )
    st.markdown('<p style="font-size:0.8rem;color:#888;margin-top:2px;">AI-powered item analysis for Goodwill resellers</p>', unsafe_allow_html=True)

    input_mode = st.segmented_control(
        "Input mode",
        options=["📷 Camera", "📁 Upload"],
        default="📷 Camera",
        label_visibility="collapsed",
    )

    image_bytes = None
    mime_type = "image/jpeg"

    if input_mode == "📷 Camera":
        photo = st.camera_input("Take a photo of the item", label_visibility="collapsed")
        if photo:
            image_bytes = photo.getvalue()
            mime_type = "image/jpeg"
    else:
        uploaded = st.file_uploader(
            "Upload item photo",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )
        if uploaded:
            image_bytes = uploaded.getvalue()
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

    if image_bytes:
        if st.button("🔍 Analyze Item", type="primary"):
            with st.spinner("Analyzing with AI..."):
                try:
                    result = analyze_image(image_bytes, mime_type)
                    st.divider()
                    render_results(result)
                except json.JSONDecodeError as e:
                    st.error(f"Could not parse AI response. Try again. ({e})")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
    else:
        st.markdown("""
        <div style="text-align:center;padding:24px 0;color:#555;">
          <div style="font-size:2.5rem;">📸</div>
          <div style="font-size:0.85rem;margin-top:8px;">Take or upload a clear photo of the item<br>to get instant eBay insights</div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
