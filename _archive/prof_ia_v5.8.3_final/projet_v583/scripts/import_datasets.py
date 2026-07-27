#!/usr/bin/env python3
"""
Script d'importation des datasets pour Prof IA v5.8
Importe les datasets Kaggle, HuggingFace et GitHub dans ChromaDB

Usage:
    python import_datasets.py --metier TSSR --source tech_support
    python import_datasets.py --metier AIS --source siem
    python import_datasets.py --source cours_admin_reseau  # Transverse
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import pandas as pd
from loguru import logger

# Configuration
CHROMADB_PATH = "./chromadb_data"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dimensions

# Chemins des datasets
DATASETS_PATHS = {
    "kaggle": "./kaggle_datasets",
    "huggingface": "./huggingface_datasets",
    "github": "./github_datasets"
}

# Configuration des sources de données
# ARCHITECTURE ALL-IN-ONE : Une seule collection pour tout
DATASET_CONFIGS = {
    # TSSR datasets
    "tech_support": {
        "path": "kaggle_datasets/tech-support-conversations-dataset",
        "type": "csv",
        "collection": "prof_ia_all",
        "chunk_size": 500,
        "metier": "TSSR"
    },
    "customer_tickets": {
        "path": "huggingface_datasets/customer-support-tickets",
        "type": "json",
        "collection": "prof_ia_all",
        "chunk_size": 500,
        "metier": "TSSR"
    },
    
    # AIS datasets
    "siem": {
        "path": "huggingface_datasets/Advanced_SIEM_Dataset",
        "type": "json",
        "collection": "prof_ia_all",
        "chunk_size": 400,
        "metier": "AIS"
    },
    "threat_logs": {
        "path": "kaggle_datasets/cybersecurity-threat-detection-logs",
        "type": "csv",
        "collection": "prof_ia_all",
        "chunk_size": 400,
        "metier": "AIS"
    },
    
    # DevOps datasets
    "cicd_logs": {
        "path": "kaggle_datasets/ai-driven-cicd-pipeline-logs-dataset",
        "type": "csv",
        "collection": "prof_ia_all",
        "chunk_size": 500,
        "metier": "DevOps"
    },
    "devops_dataset": {
        "path": "huggingface_datasets/DEVOPS",
        "type": "json",
        "collection": "prof_ia_all",
        "chunk_size": 400,
        "metier": "DevOps"
    },
    
    # Transverse datasets
    "linux_commands": {
        "path": "kaggle_datasets/linux-terminal-commands-dataset",
        "type": "csv",
        "collection": "prof_ia_all",
        "chunk_size": 200,
        "metier": "Linux (Transverse)"
    }
}


class DatasetImporter:
    """Gestionnaire d'import des datasets dans ChromaDB"""
    
    def __init__(self, chromadb_path: str = CHROMADB_PATH):
        """
        Initialise le gestionnaire d'import
        
        Args:
            chromadb_path: Chemin du répertoire ChromaDB
        """
        logger.info(f"Initialisation du DatasetImporter...")
        
        # Créer le répertoire ChromaDB si nécessaire
        os.makedirs(chromadb_path, exist_ok=True)
        
        # Initialiser ChromaDB
        self.client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Charger le modèle d'embeddings
        logger.info(f"Chargement du modèle d'embeddings: {EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        
        logger.success("DatasetImporter initialisé avec succès")
    
    def get_or_create_collection(self, collection_name: str):
        """
        Récupère ou crée une collection ChromaDB
        
        Args:
            collection_name: Nom de la collection
            
        Returns:
            Collection ChromaDB
        """
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.info(f"Collection '{collection_name}' trouvée ({collection.count()} documents)")
        except:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": f"Prof IA - {collection_name}"}
            )
            logger.info(f"Collection '{collection_name}' créée")
        
        return collection
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Découpe un texte en chunks avec overlap
        
        Args:
            text: Texte à découper
            chunk_size: Nombre de mots par chunk
            overlap: Nombre de mots de chevauchement
            
        Returns:
            Liste de chunks
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if len(chunk.strip()) > 0:
                chunks.append(chunk)
        
        return chunks
    
    def import_csv(self, file_path: str, config: Dict[str, Any]):
        """
        Importe un fichier CSV
        
        Args:
            file_path: Chemin du fichier CSV
            config: Configuration du dataset
        """
        logger.info(f"Import CSV: {file_path}")
        
        # Trouver le fichier CSV dans le répertoire
        dataset_dir = Path(file_path)
        if not dataset_dir.exists():
            logger.error(f"Répertoire non trouvé: {dataset_dir}")
            return
        
        csv_files = list(dataset_dir.glob("*.csv"))
        if not csv_files:
            logger.error(f"Aucun fichier CSV trouvé dans: {dataset_dir}")
            return
        
        csv_file = csv_files[0]  # Prendre le premier CSV trouvé
        logger.info(f"Lecture de {csv_file.name}...")
        
        try:
            df = pd.read_csv(csv_file)
            logger.info(f"Nombre de lignes: {len(df)}")
            
            # Déterminer les colonnes de texte
            text_columns = [col for col in df.columns if df[col].dtype == 'object']
            logger.info(f"Colonnes textuelles: {text_columns}")
            
            # Préparer les collections
            collections = config["collection"] if isinstance(config["collection"], list) else [config["collection"]]
            collection_objs = [self.get_or_create_collection(coll) for coll in collections]
            
            # Traiter chaque ligne
            all_chunks = []
            all_metadatas = []
            all_ids = []
            
            for idx, row in tqdm(df.iterrows(), total=len(df), desc="Traitement"):
                # Combiner toutes les colonnes textuelles
                text = " | ".join([str(row[col]) for col in text_columns if pd.notna(row[col])])
                
                # Chunker le texte
                chunks = self.chunk_text(text, chunk_size=config["chunk_size"])
                
                for chunk_idx, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_metadatas.append({
                        "source": config["metier"],
                        "dataset": file_path,
                        "row_id": str(idx),
                        "chunk_id": str(chunk_idx)
                    })
                    all_ids.append(f"{csv_file.stem}_{idx}_{chunk_idx}")
            
            # Générer les embeddings
            logger.info(f"Génération des embeddings pour {len(all_chunks)} chunks...")
            embeddings = self.embedding_model.encode(
                all_chunks,
                show_progress_bar=True,
                batch_size=32
            ).tolist()
            
            # Ajouter aux collections
            for collection in collection_objs:
                logger.info(f"Ajout de {len(all_chunks)} chunks à '{collection.name}'...")
                collection.add(
                    documents=all_chunks,
                    embeddings=embeddings,
                    metadatas=all_metadatas,
                    ids=all_ids
                )
                logger.success(f"✅ {len(all_chunks)} chunks ajoutés à '{collection.name}'")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'import CSV: {e}")
    
    def import_json(self, file_path: str, config: Dict[str, Any]):
        """
        Importe des fichiers JSON/JSONL HuggingFace
        
        Args:
            file_path: Chemin du répertoire HuggingFace
            config: Configuration du dataset
        """
        logger.info(f"Import JSON: {file_path}")
        
        dataset_dir = Path(file_path)
        if not dataset_dir.exists():
            logger.error(f"Répertoire non trouvé: {dataset_dir}")
            return
        
        # Chercher les fichiers JSON/JSONL
        json_files = list(dataset_dir.glob("*.json")) + list(dataset_dir.glob("*.jsonl"))
        if not json_files:
            logger.error(f"Aucun fichier JSON/JSONL trouvé dans: {dataset_dir}")
            return
        
        logger.info(f"Fichiers trouvés: {[f.name for f in json_files]}")
        
        collections = config["collection"] if isinstance(config["collection"], list) else [config["collection"]]
        collection_objs = [self.get_or_create_collection(coll) for coll in collections]
        
        all_chunks = []
        all_metadatas = []
        all_ids = []
        
        for json_file in json_files:
            logger.info(f"Lecture de {json_file.name}...")
            
            try:
                # Lire le JSON
                if json_file.suffix == ".jsonl":
                    # JSONL (une ligne = un objet JSON)
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = [json.loads(line) for line in f]
                else:
                    # JSON standard
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = [data]
                
                logger.info(f"Nombre d'entrées: {len(data)}")
                
                # Traiter chaque entrée
                for idx, item in enumerate(tqdm(data, desc=f"Traitement {json_file.name}")):
                    # Extraire le texte (adapter selon la structure)
                    if isinstance(item, dict):
                        # Combiner toutes les valeurs textuelles
                        text = " | ".join([str(v) for v in item.values() if isinstance(v, (str, int, float))])
                    else:
                        text = str(item)
                    
                    # Chunker
                    chunks = self.chunk_text(text, chunk_size=config["chunk_size"])
                    
                    for chunk_idx, chunk in enumerate(chunks):
                        all_chunks.append(chunk)
                        all_metadatas.append({
                            "source": config["metier"],
                            "dataset": str(json_file.name),
                            "entry_id": str(idx),
                            "chunk_id": str(chunk_idx)
                        })
                        all_ids.append(f"{json_file.stem}_{idx}_{chunk_idx}")
            
            except Exception as e:
                logger.error(f"Erreur lors de la lecture de {json_file.name}: {e}")
        
        if all_chunks:
            # Générer les embeddings
            logger.info(f"Génération des embeddings pour {len(all_chunks)} chunks...")
            embeddings = self.embedding_model.encode(
                all_chunks,
                show_progress_bar=True,
                batch_size=32
            ).tolist()
            
            # Ajouter aux collections
            for collection in collection_objs:
                logger.info(f"Ajout de {len(all_chunks)} chunks à '{collection.name}'...")
                collection.add(
                    documents=all_chunks,
                    embeddings=embeddings,
                    metadatas=all_metadatas,
                    ids=all_ids
                )
                logger.success(f"✅ {len(all_chunks)} chunks ajoutés à '{collection.name}'")
    
    def import_markdown(self, file_path: str, config: Dict[str, Any]):
        """
        Importe un fichier Markdown
        
        Args:
            file_path: Chemin du fichier Markdown
            config: Configuration du dataset
        """
        logger.info(f"Import Markdown: {file_path}")
        
        file = Path(file_path)
        if not file.exists():
            logger.error(f"Fichier non trouvé: {file}")
            return
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                text = f.read()
            
            logger.info(f"Taille du fichier: {len(text)} caractères")
            
            # Chunker le texte
            chunks = self.chunk_text(text, chunk_size=config["chunk_size"])
            logger.info(f"Nombre de chunks: {len(chunks)}")
            
            # Préparer les métadonnées
            metadatas = [
                {
                    "source": config["metier"],
                    "dataset": file.name,
                    "chunk_id": str(i)
                }
                for i in range(len(chunks))
            ]
            
            ids = [f"{file.stem}_{i}" for i in range(len(chunks))]
            
            # Générer les embeddings
            logger.info("Génération des embeddings...")
            embeddings = self.embedding_model.encode(
                chunks,
                show_progress_bar=True,
                batch_size=32
            ).tolist()
            
            # Ajouter aux collections
            collections = config["collection"] if isinstance(config["collection"], list) else [config["collection"]]
            collection_objs = [self.get_or_create_collection(coll) for coll in collections]
            
            for collection in collection_objs:
                logger.info(f"Ajout de {len(chunks)} chunks à '{collection.name}'...")
                collection.add(
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.success(f"✅ {len(chunks)} chunks ajoutés à '{collection.name}'")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'import Markdown: {e}")
    
    def import_dataset(self, source: str):
        """
        Importe un dataset selon son nom de source
        
        Args:
            source: Nom du dataset (ex: 'tech_support', 'siem')
        """
        if source not in DATASET_CONFIGS:
            logger.error(f"Source inconnue: {source}")
            logger.info(f"Sources disponibles: {list(DATASET_CONFIGS.keys())}")
            return
        
        config = DATASET_CONFIGS[source]
        file_path = config["path"]
        file_type = config["type"]
        
        logger.info(f"=== Import du dataset: {source} ===")
        logger.info(f"Type: {file_type}")
        logger.info(f"Métier: {config['metier']}")
        logger.info(f"Collection(s): {config['collection']}")
        
        if file_type == "csv":
            self.import_csv(file_path, config)
        elif file_type == "json":
            self.import_json(file_path, config)
        elif file_type == "markdown":
            self.import_markdown(file_path, config)
        elif file_type == "pdf":
            logger.warning(f"Import PDF non implémenté. Veuillez convertir en texte manuellement.")
        else:
            logger.error(f"Type de fichier non supporté: {file_type}")
    
    def show_stats(self):
        """Affiche les statistiques des collections"""
        logger.info("=== Statistiques ChromaDB ===")
        
        try:
            collection = self.client.get_collection(name="prof_ia_all")
            count = collection.count()
            logger.info(f"Collection 'prof_ia_all': {count} documents")
            
            # Afficher la répartition par métier
            try:
                results = collection.get(include=['metadatas'])
                if results and results['metadatas']:
                    metiers = {}
                    for metadata in results['metadatas']:
                        source = metadata.get('source', 'Unknown')
                        metiers[source] = metiers.get(source, 0) + 1
                    
                    logger.info("Répartition par métier:")
                    for metier, count in sorted(metiers.items()):
                        logger.info(f"  - {metier}: {count} chunks")
            except:
                pass
                
        except:
            logger.warning("Collection 'prof_ia_all' n'existe pas encore")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Import des datasets pour Prof IA v5.8"
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Nom du dataset à importer (ex: tech_support, siem, cours_admin_reseau)"
    )
    parser.add_argument(
        "--metier",
        type=str,
        choices=["TSSR", "AIS", "DevOps"],
        help="Filtre par métier (optionnel)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Afficher les statistiques des collections"
    )
    
    args = parser.parse_args()
    
    # Initialiser l'importeur
    importer = DatasetImporter()
    
    if args.stats:
        importer.show_stats()
    else:
        # Importer le dataset
        importer.import_dataset(args.source)
        
        # Afficher les stats après import
        importer.show_stats()


if __name__ == "__main__":
    main()
