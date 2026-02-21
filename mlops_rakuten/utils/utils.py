# See: https://dagshub.com/licence.pedago/overview_mlops_wine_quality_student/src/main/src/common_utils.py

import os
from pathlib import Path
from typing import Iterable

from box import ConfigBox
from box.exceptions import BoxValueError
from loguru import logger
import pandas as pd
import yaml
import subprocess
from typing import List


def read_yaml(path_to_yaml: Path) -> ConfigBox:
    """
    Lit un fichier YAML et renvoie un ConfigBox (accès par attributs).

    Args:
        path_to_yaml (Path): chemin du fichier yaml

    Raises:
        FileNotFoundError: si le fichier n'existe pas
        ValueError: si le YAML est vide
        Exception: autres erreurs de lecture

    Returns:
        ConfigBox: contenu YAML sous forme d'objet
    """

    if not path_to_yaml.exists():
        raise FileNotFoundError(f"Le fichier YAML n'existe pas : {path_to_yaml}")

    try:
        with open(path_to_yaml, "r") as yaml_file:
            content = yaml.safe_load(yaml_file)

        if content is None:
            raise BoxValueError("empty yaml")

        logger.info(f"YAML chargé avec succès : {path_to_yaml}")
        return ConfigBox(content)

    except BoxValueError:
        raise ValueError(f"Le fichier YAML est vide : {path_to_yaml}")

    except Exception as e:
        logger.error(f"Erreur lors de la lecture de {path_to_yaml}: {e}")
        raise e


def create_directories(directories: Iterable[Path], verbose: bool = True) -> None:
    """
    Crée une liste de répertoires si elle n'existe pas déjà.

    Args:
        directories (Iterable[Path]): liste d'objets Path représentant les dossiers à créer
        verbose (bool): afficher (ou non) les logs de création
    """
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        if verbose:
            logger.info(f"Répertoire créé ou déjà existant : {directory}")


def check_file_exists(file_path: Path, check_readable: bool = True) -> bool:
    """
    Vérifie qu'un fichier existe et est lisible.

    Args:
        file_path: Chemin vers le fichier
        check_readable: Si True, tente de lire les premières lignes

    Returns:
        True si le fichier est OK, False sinon
    """
    if not file_path.exists():
        return False

    if check_readable:
        try:
            df = pd.read_csv(file_path, nrows=5)
            size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.debug(f"{file_path.name} ({size_mb:.1f} MB, {df.shape[1]} colonnes)")
            return True
        except Exception as e:
            logger.warning(f"{file_path.name} : {e}")
            return False

    return True


def check_required_data_files(
    required_files: dict[str, Path],
    show_instructions: bool = True,
) -> bool:
    """
    Vérifie la présence de fichiers de données requis.

    Args:
        required_files: Dict {description: path}
        show_instructions: Si True, affiche instructions si fichiers manquants

    Returns:
        True si tous les fichiers sont OK, False sinon
    """
    missing_files = [
        file_path.name for file_path in required_files.values() if not check_file_exists(file_path)
    ]

    if missing_files:
        logger.error("Fichiers manquants dans data/raw/ :")
        for filename in missing_files:
            logger.error(f"{filename}")

        if show_instructions:
            logger.info("\n Consultez le README (section 'Configuration des données')")

        return False

    return True


def get_latest_run_dir(parent_dir: Path) -> Path:
    """
    Retourne le sous-répertoire le plus récent (tri lexical par nom),
    en supposant un nom de type ISO-8601: YYYY-MM-DDTHH-MM-SS
    """
    if not parent_dir.exists():
        logger.error(f"Répertoire inexistant : {parent_dir}")
        raise FileNotFoundError(f"{parent_dir} n'existe pas")

    run_dirs = [d for d in parent_dir.iterdir() if d.is_dir()]

    if not run_dirs:
        logger.error(f"Aucun run trouvé dans : {parent_dir}")
        raise FileNotFoundError(f"Aucun sous-répertoire dans {parent_dir}")

    latest_dir = sorted(run_dirs)[-1]
    logger.info(f"Dernier run détecté : {latest_dir.name}")

    return latest_dir