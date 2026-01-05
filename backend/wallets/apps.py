from django.apps import AppConfig


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'

    def ready(self):
        """
        DRF EDUCATIONAL NOTE - AppConfig.ready()
        ========================================
        The ready() method is called when Django starts up and the app
        registry is fully populated. This is the recommended place to:

        - Import and connect signal handlers
        - Perform one-time startup initialization
        - Register checks or other framework extensions

        Why import signals here?
        - Signals must be connected before they can fire
        - Importing the module connects the @receiver decorators
        - ready() runs once at startup, ensuring signals are ready

        Important: Don't put slow or blocking code here - it runs on every startup.
        """
        import wallets.signals  # noqa: F401 - import connects signal handlers
