from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_production_env_template_exists():
    assert (ROOT/'.env.example').exists()
    assert not (ROOT/'.env').exists()

def test_marketing_pages_exist():
    for name in ['landing.html','demo.html','pricing.html','contact.html']:
        assert (ROOT/'templates'/'marketing'/name).exists()

def test_health_and_wsgi_exist():
    assert (ROOT/'wsgi.py').exists()
    assert (ROOT/'app'/'health.py').exists()
    health = (ROOT/'app'/'health.py').read_text(encoding='utf-8')
    assert '/health/live' in health
    assert '/health/ready' in health

def test_production_docker_assets_exist():
    assert (ROOT/'Dockerfile.production').exists()
    assert (ROOT/'docker-compose.production.yml').exists()

def test_role_workspace_service_exists():
    assert (ROOT/'role_workspace.py').exists()
