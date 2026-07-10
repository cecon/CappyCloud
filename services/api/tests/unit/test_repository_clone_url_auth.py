from app.adapters.secondary.persistence.sqlalchemy_repository_repo import _inject_token_in_url


def test_inject_token_in_azure_devops_url_with_organization_username() -> None:
    url = (
        "https://linxpostos@dev.azure.com/linxpostos/"
        "linx-postos-smartpos/_git/linx-postos-smartpos-v2"
    )

    result = _inject_token_in_url(url, "secret-pat", "azure_devops")

    assert result == (
        "https://pat:secret-pat@dev.azure.com/linxpostos/"
        "linx-postos-smartpos/_git/linx-postos-smartpos-v2"
    )


def test_inject_token_in_plain_azure_devops_url() -> None:
    url = "https://dev.azure.com/org/project/_git/repo"

    result = _inject_token_in_url(url, "secret-pat", "azure_devops")

    assert result == "https://pat:secret-pat@dev.azure.com/org/project/_git/repo"
