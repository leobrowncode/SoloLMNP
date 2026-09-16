"""Configurable subset of ANC plan de comptes 2026, not a fiscal mapping."""

INITIAL_ACCOUNTS = (
    ("108000", "Compte de l’exploitant", "EQUITY"),
    ("164000", "Emprunts auprès des établissements de crédit", "LIABILITY"),
    ("211000", "Terrains", "ASSET"),
    ("213000", "Constructions", "ASSET"),
    ("218300", "Matériel de bureau et matériel informatique", "ASSET"),
    ("218400", "Mobilier", "ASSET"),
    ("281300", "Amortissements des constructions", "ASSET"),
    ("281840", "Amortissements du mobilier", "ASSET"),
    ("401000", "Fournisseurs", "LIABILITY"),
    ("411000", "Clients", "ASSET"),
    ("512000", "Banques", "ASSET"),
    ("606000", "Achats non stockés de matières et fournitures", "EXPENSE"),
    ("615000", "Entretien et réparations", "EXPENSE"),
    ("616000", "Primes d’assurances", "EXPENSE"),
    ("622000", "Rémunérations d’intermédiaires et honoraires", "EXPENSE"),
    ("627000", "Services bancaires et assimilés", "EXPENSE"),
    ("635000", "Autres impôts, taxes et versements assimilés", "EXPENSE"),
    ("661000", "Charges d’intérêts", "EXPENSE"),
    ("681100", "Dotations aux amortissements sur immobilisations", "EXPENSE"),
    ("706000", "Prestations de services", "INCOME"),
)
INITIAL_JOURNALS = (
    ("OD", "Opérations diverses", "GENERAL"),
    ("BQ", "Banque", "BANK"),
    ("AC", "Achats", "PURCHASE"),
    ("VE", "Ventes", "SALES"),
    ("AN", "À-nouveaux", "OPENING"),
)
