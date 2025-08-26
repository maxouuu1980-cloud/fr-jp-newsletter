import os, sys
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .feeds import fetch_recent
from .mistral_gen import generate_sections
from .ghost_admin import create_post, publish_post

def render_html(sections, month_tag):
    env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
    tmpl = env.get_template('newsletter.html.j2')
    return tmpl.render(
        title=f'Art de Vivre Durable – FR・JP — {month_tag}',
        sections=sections,
        period=month_tag,
        generated_at=datetime.utcnow().isoformat() + 'Z',
        now=datetime.utcnow()  # ✅ on passe "now" au template
    )

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('--month','-m'):
        month = sys.argv[2]
    else:
        month = datetime.utcnow().strftime('%Y-%m')

    items = fetch_recent()
    if not items:
        print('Warning: no recent items found — proceeding with empty set (fallback content).')
        return

    sections = generate_sections(items)
    html = render_html(sections, month)

    os.makedirs('output', exist_ok=True)
    out_path = f'output/newsletter_{month}.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Rendered:', out_path)

    publish_mode = os.getenv('PUBLISH_MODE', 'draft').lower()
    send_email = publish_mode == 'publish' and bool(os.getenv('GHOST_NEWSLETTER_SLUG'))
    post = create_post(html, f'Art de Vivre Durable — {month}', tags=['fr-jp','newsletter', month], status='draft', send_email=False)
    print('Draft created:', post['id'])

    if publish_mode == 'publish':
        pub = publish_post(post['id'], post['updated_at'], send_email=send_email, newsletter_slug=os.getenv('GHOST_NEWSLETTER_SLUG'))
        print('Published:', pub['id'])

if __name__ == '__main__':
    main()
