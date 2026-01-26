# mlops_rakuten/pipelines/data_transformation.py
from pathlib import Path

from loguru import logger

from mlops_rakuten.config.config_manager import ConfigurationManager
from mlops_rakuten.modules.data_transformation import DataTransformation


class DataTransformationPipeline:
    """
    Pipeline de transformation des données :
    - charge la configuration
    - exécute l'étape DataTransformation
    - renvoie le dossier contenant les artefacts transformés
    """

    def run(self) -> Path:
        logger.info("Démarrage du pipeline DataTransformation")

        config_manager = ConfigurationManager()
        data_transformation_config = config_manager.get_data_transformation_config()

        step = DataTransformation(config=data_transformation_config)
        output_dir = step.run()

        logger.success(
            f"Pipeline DataTransformation terminé. Artefacts disponibles dans : {output_dir}"
        )
        return output_dir

if __name__ == "__main__":
    pipeline = DataTransformationPipeline()
    pipeline.run()