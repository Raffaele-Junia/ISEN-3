"""CyberScope : vérifie si un lien est sûr avant de cliquer."""

import truststore

# Utilise le magasin de certificats du système (Windows, macOS, Linux) plutôt
# que celui de certifi : indispensable derrière un antivirus ou un proxy qui
# inspecte le HTTPS, sinon toutes les requêtes sortantes échouent.
truststore.inject_into_ssl()

__version__ = "0.2.0"
