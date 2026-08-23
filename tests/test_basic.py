"""Basic smoke and unit tests for MaterialHub."""
import pytest
from models import AccessLevel, generate_document_number  # if available, else skip
from utils import generate_document_number as gen_doc, role_required
from ai_analysis import predict_stock_needs, predict_delivery_risk


def test_index_page(client):
    """Home page should return 200."""
    response = client.get('/')
    assert response.status_code == 200


def test_login_page(client):
    """Login page should be reachable."""
    response = client.get('/auth/login')
    assert response.status_code == 200


def test_privacy_policy(client):
    response = client.get('/privacy_policy')
    assert response.status_code == 200


def test_terms_of_service(client):
    response = client.get('/terms_of_service')
    assert response.status_code == 200


def test_generate_document_number():
    """Document number generator produces correct format."""
    assert gen_doc('MR', 0) == 'MR-0001'
    assert gen_doc('PO', 41) == 'PO-0042'
    assert gen_doc('DLV', 999) == 'DLV-1000'


def test_predict_stock_needs_empty():
    """Empty inventory should return empty predictions."""
    result = predict_stock_needs([])
    assert result == []


def test_access_level_enum():
    """AccessLevel enum values are correct."""
    assert AccessLevel.supplier.value == 'supplier'
    assert AccessLevel.project_manager.value == 'project_manager'
    assert len(AccessLevel) >= 7
