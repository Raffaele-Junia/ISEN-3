from pydantic import BaseModel, Field
from datetime import date
from typing import Literal, List, Optional

class Commande(BaseModel):
    id_commande: int = Field(gt=0)
    date: date
    client_email: str
    ref: str
    quantite: int = Field(ge=1, le=100)
    prix_unitaire: float = Field(gt=0.0)
    statut: Literal["payee", "expediee", "annulee"]

class Dimensions(BaseModel):
    largeur_cm: float = Field(gt=0.0)
    hauteur_cm: float = Field(gt=0.0)

class Produit(BaseModel):
    ref: str
    nom: str
    prix: float = Field(gt=0.0)
    stock: int = Field(ge=0)
    categories: List[str] = Field(default_factory=list)
    dimensions: Optional[Dimensions] = None

class Catalogue(BaseModel):
    fournisseur: str
    mise_a_jour: date
    produits: List[Produit]

class Config(BaseModel):
    commandes: str
    catalogue: str
    sortie: str = "out"
    tva: float = Field(ge=0.0, le=1.0, default=0.20)
    seuil_alerte_stock: int = Field(ge=0, default=5)