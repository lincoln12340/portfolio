import re
import markdown2

def fix_html_with_embedded_markdown(text):
    """
    Detects markdown sections embedded within mostly-HTML output,
    converts them to HTML, and replaces them in the text.
    """
    if not text:
        return text

    # Don't touch it if it's a fully valid HTML document
    if bool(re.search(r'<html', text, re.IGNORECASE)):
        return text

    # Pattern to detect markdown-style headings, lists, bold, etc.
    markdown_blocks = list(re.finditer(
        r'(?:(^|\n)(\s*)(#{1,6} .+|[-*+] .+|\d+\..+|>\s.+|\*\*.+\*\*|__.+__)([\s\S]+?))(?=\n{2,}|\Z)', 
        text,
        flags=re.MULTILINE
    ))

    # Convert and replace each markdown block
    for match in reversed(markdown_blocks):  # reversed to not break indices when replacing
        md_block = match.group(0).strip()
        # Only convert if not inside an HTML tag already
        if not re.match(r'<[a-z][^>]*>', md_block):
            html_block = markdown2.markdown(md_block)
            # Optionally strip <p> if markdown2 wraps the entire block
            if html_block.startswith('<p>') and html_block.endswith('</p>\n'):
                html_block = html_block[3:-5]
            # Replace markdown block with HTML
            start, end = match.span(0)
            text = text[:start] + html_block + text[end:]

    return text

test_input = """
<div class="container">
  <h1>Comprehensive Investment Analysis</h1>
  <div class="section">
    <h2>Executive Summary</h2>
    <div class="summary-box">
      <p>This section is already valid HTML. The analysis covers all key fundamentals.</p>
    </div>
    <div class="recommendation buy">
      RECOMMENDATION: BUY
    </div>
  </div>

  <div class="section">
    <h2>Fundamental Analysis</h2>
    <div>
      **Revenues:** $1.2B  
      **Income:** $350M  
      - Margin expansion in 2025  
      - No significant debt  
    </div>
  </div>

  <div class="section">
    <h2>Technical Analysis</h2>
    <p>This area is clean HTML and should not be changed.</p>
    <ul>
      <li>SMA: 50-day trending up</li>
      <li>RSI: 62</li>
    </ul>
    #### Key Technical Signals
    * Strong upward momentum
    * Support at $110
    * Resistance at $125
  </div>

  <div class="section">
    <h2>News and Events Analysis</h2>
    [Q2 earnings beat expectations](https://news.com/q2-beat)
    - Announced new product line
    - CEO interview on <a href="https://finance.tv">Finance TV</a>
  </div>

  <div class="section">
    <h2>Already HTML</h2>
    <div class="metrics">
      <div class="metric-card">
        <div class="metric-title">Assets</div>
        <div class="metric-value">$3B</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Liabilities</div>
        <div class="metric-value">$700M</div>
      </div>
    </div>
  </div>
</div>
"""

#html_content = response.choices[0].message.content
clean_html = fix_html_with_embedded_markdown(test_input)
print(clean_html)

