"""
Test Suite for Miracle Hostel Management Portal - Dark Mode Support.
Verifies:
1. Color-scheme meta tag present across base layout and login template.
2. Anti-FOUC inline scripts present in head of templates to avoid flashing.
3. Theme toggle controls present in Topbar header, User menu dropdown, and Login view.
4. CSS custom property tokens defined for both :root and [data-bs-theme="dark"].
5. Theme switching logic in main.js with localStorage persistence and OS preference sync.
"""
import os
import pytest
from app import create_app
from app.extensions import db
from app.models import Admin


@pytest.fixture
def app():
    """Create testing application context."""
    test_app = create_app('testing')
    with test_app.app_context():
        db.create_all()
        admin = Admin(
            email="admin@123",
            username="admin",
            is_active=True
        )
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()

        yield test_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Unauthenticated client fixture."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Authenticated administrator client fixture."""
    c = app.test_client()
    c.post('/auth/login', data={
        'email': 'admin@123',
        'password': '1234'
    }, follow_redirects=True)
    return c


def test_login_dark_mode_support(client):
    """Test login page includes color-scheme meta, anti-FOUC script, and theme toggle button."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert '<meta name="color-scheme" content="light dark">' in html
    assert 'miracle_theme' in html
    assert 'data-bs-theme' in html
    assert 'id="themeToggleBtn"' in html
    assert 'theme-icon-dark' in html
    assert 'theme-icon-light' in html


def test_base_layout_dark_mode_meta_and_script(auth_client):
    """Test authenticated dashboard includes color-scheme meta and anti-FOUC script."""
    response = auth_client.get('/')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert '<meta name="color-scheme" content="light dark">' in html
    assert 'miracle_theme' in html
    assert 'data-bs-theme' in html
    assert 'prefers-color-scheme' in html


def test_topbar_theme_toggle_controls(auth_client):
    """Test topbar contains header button and dropdown menu toggle option."""
    response = auth_client.get('/')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'id="themeToggleBtn"' in html
    assert 'theme-icon-dark' in html
    assert 'theme-icon-light' in html
    assert 'id="themeToggleDropdownBtn"' in html
    assert 'theme-mode-label' in html


def test_css_tokens_and_dark_theme_definitions():
    """Verify style.css, dashboard.css, and responsive.css define theme tokens and avoid hardcoded surfaces."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    style_css_path = os.path.join(base_dir, 'app', 'static', 'css', 'style.css')
    dashboard_css_path = os.path.join(base_dir, 'app', 'static', 'css', 'dashboard.css')
    responsive_css_path = os.path.join(base_dir, 'app', 'static', 'css', 'responsive.css')

    with open(style_css_path, 'r', encoding='utf-8') as f:
        style_css = f.read()
    with open(dashboard_css_path, 'r', encoding='utf-8') as f:
        dashboard_css = f.read()
    with open(responsive_css_path, 'r', encoding='utf-8') as f:
        responsive_css = f.read()

    # Verify style.css dark theme definition
    assert 'color-scheme: light dark;' in style_css
    assert '[data-bs-theme="dark"]' in style_css
    assert '--color-surface: #1E293B;' in style_css
    assert '--color-bg: #0B1120;' in style_css
    assert '[data-bs-theme="dark"] .bg-white' in style_css
    assert '[data-bs-theme="dark"] .bg-light' in style_css
    assert '[data-bs-theme="dark"] .text-dark' in style_css

    # Verify dashboard.css consumes semantic surface tokens
    assert '.app-sidebar {\n  width: var(--sidebar-width);\n  background-color: var(--color-surface);' in dashboard_css
    assert 'background-color: var(--color-surface);' in dashboard_css

    # Verify responsive.css mobile drawer and table use semantic surface variables
    assert 'background-color: var(--color-surface);' in responsive_css
    assert 'background-color: var(--color-surface-hover)' in responsive_css


def test_js_theme_toggle_implementation():
    """Verify main.js includes theme initialization, storage sync, and OS preference listener."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_js_path = os.path.join(base_dir, 'app', 'static', 'js', 'main.js')

    with open(main_js_path, 'r', encoding='utf-8') as f:
        main_js = f.read()

    assert 'initThemeToggle()' in main_js
    assert 'miracle_theme' in main_js
    assert 'data-bs-theme' in main_js
    assert 'prefers-color-scheme' in main_js
    assert 'toggleTheme()' in main_js
    assert "window.addEventListener('storage'" in main_js
