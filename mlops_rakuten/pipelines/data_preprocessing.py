from pathlib import Path

from loguru import logger

from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.modules.data_preprocessing import DataPreprocessing


class DataPreprocessingPipeline:
    """
    Pipeline de prétraitement des données :
    - charge la configuration
    - exécute l'étape DataPreprocessing
    - renvoie le chemin du dataset prétraité
    """

    def run(self) -> Path:
        logger.info("Démarrage du pipeline DataPreprocessing")

        config_manager = ConfigurationManager()
        data_preprocessing_config = config_manager.get_data_preprocessing_config()

        step = DataPreprocessing(config=data_preprocessing_config)
        output_path = step.run()

        logger.success(f"Pipeline DataPreprocessing terminé. Fichier créé : {output_path}")
        return output_path

if __name__ == "__main__":
    pipeline = DataPreprocessingPipeline()
    pipeline.run()