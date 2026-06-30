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
  .block-container { padding: 3.5rem 0.75rem 1rem; max-width: 100%; }
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

Before pricing, use the web_search tool to look up actual current and recently-sold eBay listings (and other resale comps like WorthPoint, Etsy, or Replacements.com if useful) for this specific item, brand, and pattern/model. Search using the brand, model/pattern name, and item type you identify from the photo (e.g. "Wedgwood Jasperware vase sold price ebay" or "Fiesta Ware cobalt blue dinner plate ebay sold"). Ground your price estimate in what you actually find rather than guessing from memory. If you cannot find a clean match, search more broadly (by category, material, era) and note the lower confidence.

Also use web_search to try to find a reference photo of the exact pattern/model you identified (e.g. on Replacements.com, an eBay listing, a collector reference site, or Etsy), so the user can visually compare it against their own item. Prefer direct image URLs (ending in .jpg/.jpeg/.png/.webp) when you find one, or a page URL that prominently displays the pattern.

After researching, return ONLY a valid JSON object with exactly these fields (no markdown, no explanation):

{
  "item_name": "Specific descriptive name of the item",
  "category": "eBay category (e.g. Pottery & Glass, Collectibles, Clothing, Electronics, etc.)",
  "era": "antique" or "vintage" or "modern",
  "era_note": "antique = 100+ years old, vintage = 20-100 years old, modern = less than 20 years old",
  "estimated_period": "e.g. 1920s-1940s or Victorian Era or 1990s",
  "brand_or_maker": "Brand, maker, or manufacturer if visible or identifiable, else null",
  "model_name": "Specific model, pattern, or line name. Critical for: flatware (e.g. 'Oneida Community Silverplate Paul Revere'), plates/china (e.g. 'Johnson Brothers Old Britain Castles Blue'), stoneware/pottery (e.g. 'McCoy Pottery Canyon Pattern', 'Fiesta Ware Cobalt Blue'), porcelain (e.g. 'Wedgwood Jasperware', 'Delft Blue Windmill'), crystal & glassware (e.g. 'Waterford Lismore Goblet', 'Fostoria American', 'Cambridge Rose Point'), toys (e.g. 'Hot Wheels 1969 Custom Camaro', 'Fisher-Price Little People Farm #915', 'Kenner Star Wars Millennium Falcon', 'Marx Tin Litho Truck'), stuffed animals (e.g. 'Steiff Teddy Bear with Button in Ear', 'Ty Beanie Baby Princess Bear 1997', 'Gund Snuffles Bear', 'Dakin Dream Pets'), vintage electronics, etc. Look for backstamps, molded marks, copyright dates, sewn-in labels, hang tags, or button/ear tags. Return null only if truly unidentifiable.",
  "materials": ["list", "of", "materials"],
  "dominant_colors": ["color1", "color2"],
  "color_hex": ["#hex1", "#hex2"],
  "condition": "Excellent" or "Very Good" or "Good" or "Fair" or "Poor",
  "condition_notes": "Brief description of visible condition issues or highlights",
  "pieces_in_photo": 1,
  "ebay_price_low": 5,
  "ebay_price_high": 45,
  "price_basis_note": "Brief note confirming this price is per single piece, e.g. 'Per plate' or 'Per goblet — sets of 4+ sell for more per-piece as a lot'",
  "price_sources": "Brief summary of what you found via web search that informed this price, e.g. 'Based on 3 sold listings on eBay for this pattern, $18-$32 per plate' — or 'No close match found; estimate based on similar Fiesta Ware pricing' if search was inconclusive",
  "listing_title": "Suggested eBay listing title (max 80 chars, keyword-rich)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7", "keyword8"],
  "selling_tips": ["tip1", "tip2", "tip3"],
  "suggested_size": "Your best estimate of the item's size/dimensions if not provided by the user (e.g. '10 inch dinner plate', '12 oz goblet', '8 inch bowl') — important for pricing accuracy",
  "notable_features": ["feature1", "feature2"],
  "authenticity_markers": "What to check to verify authenticity or age, or null if not applicable",
  "reference_image_url": "Direct URL to a photo of this exact pattern/model found via web search, for visual comparison, or null if none found",
  "reference_source_url": "URL of the page the reference image came from (for attribution/context), or null",
  "pattern_match_notes": "Brief note on how confident the pattern/model match is and what visual details support it, or null if no model_name was identified",
  "confidence": "high" or "medium" or "low"
}

Rules:
- model_name is ESPECIALLY important for: flatware/silverware (hallmarks, Rogers, Oneida, Reed & Barton, Gorham), plates/dinnerware/china (backstamp patterns — Blue Willow, Ironstone, Transferware), stoneware & pottery (impressed/painted marks — McCoy, Roseville, Hull, Red Wing, Fiesta Ware, Bauer, Frankoma), porcelain (Wedgwood, Spode, Meissen, Limoges), crystal & glassware (Waterford, Lenox, Baccarat, Fostoria, Cambridge, Heisey, Depression Glass — lead crystal vs. crystal vs. glass distinction matters for value), toys (Hot Wheels/Matchbox model name+year on base, Fisher-Price model number, LEGO set number, Marx/Ideal/Kenner/Hasbro/Mattel markings, tin toy origin markings, action figure copyright year+maker molded into plastic, cast iron toy maker), stuffed animals (Steiff button-in-ear + chest tag = high value; Ty Beanie Baby tag generation affects value greatly — 1st/2nd gen tags worth far more; Gund, Dakin, Rushton, Hermann, Boyds Bears sewn labels; character plush — look for Disney/Warner Bros tags), and vintage electronics. If the photo does NOT show the base/tag/label, note it in authenticity_markers with specific instructions (e.g. "Check button in ear and chest tag" for bears, "Turn over — model number molded into base" for toys, "Photograph foot rim for acid-etched signature" for crystal).
- era must be exactly one of: antique, vintage, modern
- pieces_in_photo: count the actual number of individual items visible in the photo (e.g. a stack of 4 plates = 4, a single goblet = 1)
- ebay_price_low and ebay_price_high MUST be the price for ONE SINGLE PIECE, regardless of how many pieces are in the photo — never the price for the whole group/set/lot
- When mentally referencing comparable eBay sold listings, many results are for lots/sets (e.g. "set of 8 forks $60" or "4 wine glasses $40") — divide by the number of pieces in that comparable listing before using it as a reference point. Do not anchor on a lot's total price.
- If pieces_in_photo > 1, still report ebay_price_low/high as the PER-PIECE range, and use price_basis_note to flag that selling as a complete set/lot may fetch a different total than per-piece price times quantity
- listing_title should include era, material, color, and use when applicable
- keywords should be actual eBay search terms buyers would use
- selling_tips should be actionable advice (photography angles, timing, bundling, etc.)
- If you cannot identify the item clearly, set confidence to "low" and still fill all fields with best guesses
- color_hex should have the same length as dominant_colors"""


def encode_image(image_bytes: bytes, mime_type: str) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def analyze_image(
    image_bytes: bytes,
    mime_type: str,
    manual_notes: str = "",
    item_size: str = "",
    back_bytes: bytes = None,
    back_mime: str = "image/jpeg",
) -> dict:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    prompt = ANALYZE_PROMPT
    if item_size.strip():
        prompt += f"\n\nITEM SIZE PROVIDED BY USER: {item_size.strip()}\nUse this size when estimating the eBay price range — size significantly affects value for plates, bowls, platters, and glassware."
    if manual_notes.strip():
        prompt += f"\n\nADDITIONAL INFO FROM USER (markings/text too faint to photograph):\n{manual_notes.strip()}\nUse this to refine brand_or_maker, model_name, era, and materials."

    content = [
        {"type": "text", "text": "IMAGE 1 — FRONT of item:"},
        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": encode_image(image_bytes, mime_type)}},
    ]
    if back_bytes:
        content += [
            {"type": "text", "text": "IMAGE 2 — BACK of item (may contain maker's mark, backstamp, hallmark, or model number):"},
            {"type": "image", "source": {"type": "base64", "media_type": back_mime, "data": encode_image(back_bytes, back_mime)}},
        ]
    content.append({"type": "text", "text": prompt})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": content}],
    )

    raw = ""
    for block in response.content:
        if block.type == "text":
            raw = block.text

    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        return json.loads(json_match.group())
    raise ValueError(f"Could not parse JSON from response: {raw[:300]}")


def era_badge(era: str) -> str:
    label = {"antique": "ANTIQUE (100+ yrs)", "vintage": "VINTAGE (20-100 yrs)", "modern": "MODERN"}.get(era.lower(), era.upper())
    css_class = f"era-{era.lower()}"
    return f'<span class="era-badge {css_class}">{label}</span>'


def render_results(data: dict, user_photo: bytes = None):
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
    pieces = data.get("pieces_in_photo", 1)
    price_basis = data.get("price_basis_note", "")
    st.markdown(f"""
    <div class="price-box">
      <div class="price-label">Estimated eBay Price — Per Piece</div>
      <div class="price-value">${price_low} – ${price_high}</div>
    </div>
    """, unsafe_allow_html=True)
    if pieces and pieces > 1:
        st.markdown(f'<div style="font-size:0.78rem;color:#FFEB3B;text-align:center;margin-top:-6px;">📦 {pieces} pieces detected in photo — price above is PER PIECE, not for the whole group</div>', unsafe_allow_html=True)
    if price_basis:
        st.markdown(f'<div style="font-size:0.75rem;color:#888;text-align:center;margin-top:2px;">{price_basis}</div>', unsafe_allow_html=True)

    price_sources = data.get("price_sources")
    if price_sources:
        st.markdown(f'<div style="font-size:0.72rem;color:#00BFFF;text-align:center;margin-top:6px;">🔎 {price_sources}</div>', unsafe_allow_html=True)

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

    ref_image = data.get("reference_image_url")
    ref_source = data.get("reference_source_url")
    match_notes = data.get("pattern_match_notes")
    if ref_image or match_notes:
        st.markdown('<div class="section-header">Pattern Match Reference</div>', unsafe_allow_html=True)
        if ref_image:
            col_a, col_b = st.columns(2)
            if user_photo:
                col_a.image(user_photo, caption="Your item", use_container_width=True)
            col_b.image(ref_image, caption="Reference match", use_container_width=True)
            col_b.markdown(f'<span style="font-size:0.7rem;color:#666;">If this doesn\'t load: <a href="{ref_image}" target="_blank">open image link</a></span>', unsafe_allow_html=True)
            if ref_source:
                st.markdown(f'<a href="{ref_source}" target="_blank" style="font-size:0.72rem;color:#00BFFF;">🔗 Source</a>', unsafe_allow_html=True)
        if match_notes:
            st.markdown(f'<div style="font-size:0.8rem;color:#CCCCCC;margin-top:4px;">{match_notes}</div>', unsafe_allow_html=True)

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

    suggested_size = data.get("suggested_size")
    if suggested_size:
        st.markdown('<div class="section-header">Estimated Size</div>', unsafe_allow_html=True)
        st.markdown(f'<span style="font-size:0.9rem;">📐 {suggested_size}</span>', unsafe_allow_html=True)

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


def render_correction_form(data: dict):
    with st.expander("✏️ Correct any details"):
        st.markdown('<div style="font-size:0.78rem;color:#888;margin-bottom:8px;">If the AI got something wrong (e.g. wrong brand), fix it here — your changes are reflected immediately.</div>', unsafe_allow_html=True)

        new_item_name = st.text_input("Item name", value=data.get("item_name", ""))
        new_category = st.text_input("Category", value=data.get("category", ""))

        col1, col2 = st.columns(2)
        new_brand = col1.text_input("Brand / Maker", value=data.get("brand_or_maker") or "")
        new_model = col2.text_input("Pattern / Model", value=data.get("model_name") or "")

        era_options = ["antique", "vintage", "modern"]
        current_era = (data.get("era") or "modern").lower()
        new_era = st.segmented_control("Era", era_options, default=current_era if current_era in era_options else "modern")

        col3, col4 = st.columns(2)
        new_price_low = col3.number_input("Price low ($)", value=float(data.get("ebay_price_low") or 0), min_value=0.0, step=1.0)
        new_price_high = col4.number_input("Price high ($)", value=float(data.get("ebay_price_high") or 0), min_value=0.0, step=1.0)

        new_condition_notes = st.text_area("Condition notes", value=data.get("condition_notes", ""), height=70)

        if st.button("✅ Apply Corrections"):
            data["item_name"] = new_item_name
            data["category"] = new_category
            data["brand_or_maker"] = new_brand or None
            data["model_name"] = new_model or None
            data["era"] = new_era
            data["ebay_price_low"] = new_price_low
            data["ebay_price_high"] = new_price_high
            data["condition_notes"] = new_condition_notes
            st.session_state.result = data
            st.rerun()


def main():
    st.markdown(
        '<h1 style="margin-bottom:0;">🔍 <span style="color:#FFEB3B;">eBay</span> <span style="color:#00BFFF;">Item</span> Identifier</h1>',
        unsafe_allow_html=True,
    )
    st.markdown('<p style="font-size:0.8rem;color:#888;margin-top:2px;">AI-powered item analysis for Goodwill resellers</p>', unsafe_allow_html=True)

    input_mode = st.segmented_control(
        "Input mode",
        options=["📁 Upload", "📷 Camera"],
        default="📁 Upload",
        label_visibility="collapsed",
    )
    if input_mode == "📁 Upload":
        st.markdown('<div style="font-size:0.72rem;color:#666;margin-bottom:6px;">Tap "Browse files" → "Take Photo" to use your rear camera</div>', unsafe_allow_html=True)

    image_bytes = None
    mime_type = "image/jpeg"
    back_bytes = None
    back_mime = "image/jpeg"

    def mime_from_ext(name):
        ext = name.rsplit(".", 1)[-1].lower()
        return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

    if input_mode == "📷 Camera":
        st.markdown('<div style="font-size:0.78rem;color:#00BFFF;font-weight:600;margin-bottom:4px;">FRONT</div>', unsafe_allow_html=True)
        photo_front = st.camera_input("Front of item", label_visibility="collapsed", key="cam_front")
        if photo_front:
            image_bytes = photo_front.getvalue()

        st.markdown('<div style="font-size:0.78rem;color:#888;font-weight:600;margin:10px 0 4px;">BACK <span style="color:#555;font-weight:400;">(optional — for maker\'s mark)</span></div>', unsafe_allow_html=True)
        photo_back = st.camera_input("Back of item", label_visibility="collapsed", key="cam_back")
        if photo_back:
            back_bytes = photo_back.getvalue()
    else:
        st.markdown('<div style="font-size:0.78rem;color:#00BFFF;font-weight:600;margin-bottom:4px;">FRONT</div>', unsafe_allow_html=True)
        uploaded_front = st.file_uploader("Front photo", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed", key="up_front")
        if uploaded_front:
            image_bytes = uploaded_front.getvalue()
            mime_type = mime_from_ext(uploaded_front.name)
            st.image(uploaded_front, use_container_width=True)

        st.markdown('<div style="font-size:0.78rem;color:#888;font-weight:600;margin:10px 0 4px;">BACK <span style="color:#555;font-weight:400;">(optional — for maker\'s mark)</span></div>', unsafe_allow_html=True)
        uploaded_back = st.file_uploader("Back photo", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed", key="up_back")
        if uploaded_back:
            back_bytes = uploaded_back.getvalue()
            back_mime = mime_from_ext(uploaded_back.name)
            st.image(uploaded_back, use_container_width=True)

    if image_bytes:
        with st.expander("📐 Item size (optional — improves pricing)"):
            st.markdown('<div style="font-size:0.78rem;color:#888;margin-bottom:6px;">Measure or estimate the size. Affects price for plates, bowls, platters, glassware, and more.</div>', unsafe_allow_html=True)
            size_presets = ["", "Demitasse / espresso (3–4\")", "Bread & butter plate (6\")", "Salad plate (7–8\")", "Luncheon plate (9\")", "Dinner plate (10–11\")", "Charger / service plate (12–13\")", "Platter / oval serving (14\"+)", "Juice glass (4–6 oz)", "Rocks / lowball glass (6–8 oz)", "Highball / tumbler (10–14 oz)", "Wine glass (8–12 oz)", "Goblet (12–16 oz)", "Decanter / pitcher (varies)", "Other (type below)"]
            size_choice = st.selectbox("Common sizes", size_presets, label_visibility="collapsed")
            size_custom = st.text_input("Or type exact size / dimensions", placeholder='e.g. "10.5 inch diameter" or "9 oz goblet"', label_visibility="collapsed")
            item_size = size_custom.strip() if size_custom.strip() else (size_choice if size_choice else "")

        with st.expander("✏️ Add markings or text (optional)"):
            st.markdown('<div style="font-size:0.78rem;color:#888;margin-bottom:6px;">Type anything you can read on the item that may not show clearly in the photo — backstamp, etched signature, pattern name, country of origin, model number, hallmarks, etc.</div>', unsafe_allow_html=True)
            manual_notes = st.text_area(
                "Markings / text on item",
                placeholder="e.g. 'Made in England • Johnson Brothers' or 'Waterford Ireland' etched on base, or '925 Sterling' stamp inside band",
                height=100,
                label_visibility="collapsed",
            )

        if st.button("🔍 Analyze Item", type="primary"):
            with st.spinner("Analyzing with AI..."):
                try:
                    st.session_state.result = analyze_image(image_bytes, mime_type, manual_notes, item_size, back_bytes, back_mime)
                    st.session_state.user_photo = image_bytes
                except json.JSONDecodeError as e:
                    st.error(f"Could not parse AI response. Try again. ({e})")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

        if st.session_state.get("result"):
            st.divider()
            render_results(st.session_state.result, st.session_state.get("user_photo"))
            render_correction_form(st.session_state.result)
    else:
        st.markdown("""
        <div style="text-align:center;padding:24px 0;color:#555;">
          <div style="font-size:2.5rem;">📸</div>
          <div style="font-size:0.85rem;margin-top:8px;">Take or upload a clear photo of the item<br>to get instant eBay insights</div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
