"""Tests for multi-tenancy system (Phase 22)."""
import pytest
from pathlib import Path


class TestTenantBilling:
    def test_import(self):
        from core.tenant_billing import TenantBilling
        assert TenantBilling is not None

    def test_plan_limits(self):
        from core.tenant_billing import TenantBilling
        billing = TenantBilling()
        # Starter plan should have limits
        starter = billing.get_plan_limits("starter")
        assert starter["max_users"] > 0
        assert starter["max_cases"] > 0

    def test_enterprise_unlimited(self):
        from core.tenant_billing import TenantBilling
        billing = TenantBilling()
        enterprise = billing.get_plan_limits("enterprise")
        assert enterprise["max_users"] == -1 or enterprise["max_users"] > 1000

    def test_check_quota(self, tmp_path):
        from core.tenant_billing import TenantBilling
        billing = TenantBilling(str(tmp_path))
        result = billing.check_quota("tenant-1", "starter", "users", 3)
        assert "allowed" in result


class TestTenantTheming:
    def test_import(self):
        from core.tenant_theming import TenantTheme, get_theme
        assert TenantTheme is not None

    def test_default_theme(self):
        from core.tenant_theming import get_default_theme
        theme = get_default_theme()
        assert theme.primary_color is not None
        assert theme.font_family is not None

    def test_css_vars(self):
        from core.tenant_theming import get_default_theme, get_theme_css_vars
        theme = get_default_theme()
        css = get_theme_css_vars(theme)
        assert "--primary" in css or "primary" in str(css)


class TestSSOConfig:
    def test_import(self):
        from core.sso_config import SSOConfig, get_sso_config
        assert SSOConfig is not None
        assert get_sso_config is not None
