class BanqueError(Exception):
    pass

class MontantInvalideError(BanqueError):
    pass

class SoldeInsuffisantError(BanqueError):
    pass