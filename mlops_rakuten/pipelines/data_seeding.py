from pathlib import Path

from loguru import logger

from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.modules.data_seeding import DataSeeding


class DataSeedingPipeline:
    """
    Pipeline de seeding des données :
    - charge la configuration
    - exécute l'étape DataSeeding
    - renvoie le chemin du dataset initial
    """

    def run(self) -> Path:
        logger.info("Démarrage du pipeline DataSeeding")

        config_manager = ConfigurationManager()
        data_seeding_config = config_manager.get_data_seeding_config()

        step = DataSeeding(config=data_seeding_config)
        output_path = step.run()

        logger.success(f"Pipeline DataIngestion terminé. Fichier créé : {output_path}")
        return output_path

if __name__ == "__main__":
    pipeline = DataSeedingPipeline()
    pipeline.run()