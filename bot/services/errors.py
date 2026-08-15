class ResolutionError(Exception):
    """Erreur métier lors de la résolution vague/membre/semaine — message destiné
    à être affiché tel quel à l'appelant (Discord ephemeral ou HTTP 404)."""
