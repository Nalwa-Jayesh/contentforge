import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import chromadb
from chromadb.config import Settings
from models.content_models import ContentVersion, ContentStatus, AgentType
from utils.logger import logger
from config import Config

class VersionManager:
    """Manages content versions using ChromaDB with RL-based search"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(Config.CHROMA_DB_PATH)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name=Config.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"Version manager initialized with database at: {self.db_path}")
    
    def save_version(self, version: ContentVersion) -> bool:
        """
        Save a content version to ChromaDB
        
        Args:
            version: ContentVersion to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate version
            if not version.id or not version.chapter_id:
                logger.error("Invalid version: missing required fields")
                return False
                
            if not version.content:
                logger.error(f"Invalid version {version.id}: empty content")
                return False
            
            # Prepare metadata for ChromaDB
            metadata = {
                "version_id": version.id,
                "chapter_id": version.chapter_id,
                "status": version.status.value,
                "agent_type": version.agent_type.value,
                "created_at": version.created_at.isoformat(),
                "parent_version_id": version.parent_version_id or "",
                "content_length": len(version.content),
                "content_hash": version.get_content_hash()
            }
            
            # Add metadata fields, ensuring datetime objects are converted
            for key, value in version.metadata.items():
                if isinstance(value, datetime):
                    metadata[f"meta_{key}"] = value.isoformat()
                else:
                    metadata[f"meta_{key}"] = str(value)
            
            # Add to collection
            self.collection.add(
                documents=[version.content],
                metadatas=[metadata],
                ids=[version.id]
            )
            
            logger.info(f"Saved version {version.id} for chapter {version.chapter_id} "
                       f"(status: {version.status.value}, length: {len(version.content)})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving version {version.id}: {str(e)}")
            return False
    
    def get_version(self, version_id: str) -> Optional[ContentVersion]:
        """
        Retrieve a specific version by ID
        
        Args:
            version_id: ID of the version to retrieve
            
        Returns:
            ContentVersion if found, None otherwise
        """
        try:
            result = self.collection.get(ids=[version_id])
            
            if not result['documents'] or not result['documents'][0]:
                logger.warning(f"Version {version_id} not found")
                return None
            
            metadata = result['metadatas'][0]
            content = result['documents'][0]
            
            # Reconstruct metadata dictionary
            version_metadata = {}
            for key, value in metadata.items():
                if key.startswith("meta_"):
                    version_metadata[key[5:]] = value
            
            version = ContentVersion(
                id=metadata['version_id'],
                chapter_id=metadata['chapter_id'],
                content=content,
                status=ContentStatus(metadata['status']),
                agent_type=AgentType(metadata['agent_type']),
                metadata=version_metadata,
                created_at=datetime.fromisoformat(metadata['created_at']),
                parent_version_id=metadata['parent_version_id'] if metadata['parent_version_id'] else None
            )
            
            return version
            
        except Exception as e:
            logger.error(f"Error retrieving version {version_id}: {str(e)}")
            return None
    
    def get_chapter_versions(self, chapter_id: str) -> List[ContentVersion]:
        """
        Get all versions for a specific chapter
        
        Args:
            chapter_id: ID of the chapter
            
        Returns:
            List of ContentVersions for the chapter
        """
        try:
            result = self.collection.get(
                where={"chapter_id": chapter_id}
            )
            
            versions = []
            for i, doc in enumerate(result['documents']):
                metadata = result['metadatas'][i]
                
                # Reconstruct metadata dictionary
                version_metadata = {}
                for key, value in metadata.items():
                    if key.startswith("meta_"):
                        version_metadata[key[5:]] = value
                
                version = ContentVersion(
                    id=metadata['version_id'],
                    chapter_id=metadata['chapter_id'],
                    content=doc,
                    status=ContentStatus(metadata['status']),
                    agent_type=AgentType(metadata['agent_type']),
                    metadata=version_metadata,
                    created_at=datetime.fromisoformat(metadata['created_at']),
                    parent_version_id=metadata['parent_version_id'] if metadata['parent_version_id'] else None
                )
                versions.append(version)
            
            # Sort by creation time
            versions.sort(key=lambda x: x.created_at)
            logger.info(f"Retrieved {len(versions)} versions for chapter {chapter_id}")
            return versions
            
        except Exception as e:
            logger.error(f"Error retrieving versions for chapter {chapter_id}: {str(e)}")
            return []
    
    def search_similar_content(self, query: str, chapter_id: Optional[str] = None, 
                             n_results: int = None, status_filter: Optional[str] = None) -> List[Tuple[ContentVersion, float]]:
        """
        Search for similar content using vector similarity
        
        Args:
            query: Text to search for
            chapter_id: Optional filter by chapter ID
            n_results: Maximum number of results to return
            status_filter: Optional filter by content status
            
        Returns:
            List of tuples (ContentVersion, similarity_score)
        """
        n_results = n_results or Config.MAX_SEARCH_RESULTS
        
        try:
            # Build where clause for filtering
            where_clause = {}
            if chapter_id:
                where_clause["chapter_id"] = chapter_id
            if status_filter:
                where_clause["status"] = status_filter
            
            # Perform vector search
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause if where_clause else None
            )
            
            similar_versions = []
            
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    similarity = 1.0 - distance  # Convert distance to similarity
                    
                    # Skip results below threshold
                    if similarity < (1.0 - Config.SIMILARITY_THRESHOLD):
                        continue
                    
                    # Reconstruct metadata dictionary
                    version_metadata = {}
                    for key, value in metadata.items():
                        if key.startswith("meta_"):
                            version_metadata[key[5:]] = value
                    
                    version = ContentVersion(
                        id=metadata['version_id'],
                        chapter_id=metadata['chapter_id'],
                        content=doc,
                        status=ContentStatus(metadata['status']),
                        agent_type=AgentType(metadata['agent_type']),
                        metadata=version_metadata,
                        created_at=datetime.fromisoformat(metadata['created_at']),
                        parent_version_id=metadata['parent_version_id'] if metadata['parent_version_id'] else None
                    )
                    
                    similar_versions.append((version, similarity))
            
            logger.info(f"Found {len(similar_versions)} similar versions for query")
            return similar_versions
            
        except Exception as e:
            logger.error(f"Error searching similar content: {str(e)}")
            return []
    
    def get_version_tree(self, chapter_id: str) -> Dict[str, Any]:
        """
        Get the version tree for a chapter showing parent-child relationships
        
        Args:
            chapter_id: ID of the chapter
            
        Returns:
            Dictionary representing the version tree
        """
        versions = self.get_chapter_versions(chapter_id)
        
        # Build tree structure
        tree = {}
        version_map = {v.id: v for v in versions}
        
        for version in versions:
            version_info = {
                'id': version.id,
                'status': version.status.value,
                'agent_type': version.agent_type.value,
                'created_at': version.created_at.isoformat(),
                'content_length': len(version.content),
                'children': []
            }
            
            if version.parent_version_id:
                if version.parent_version_id not in tree:
                    tree[version.parent_version_id] = {
                        'id': version.parent_version_id,
                        'children': []
                    }
                tree[version.parent_version_id]['children'].append(version_info)
            else:
                # Root version
                tree[version.id] = version_info
        
        return tree
    
    def get_latest_version(self, chapter_id: str, status: Optional[ContentStatus] = None) -> Optional[ContentVersion]:
        """
        Get the latest version for a chapter, optionally filtered by status
        
        Args:
            chapter_id: ID of the chapter
            status: Optional status filter
            
        Returns:
            Latest ContentVersion or None
        """
        versions = self.get_chapter_versions(chapter_id)
        
        if status:
            versions = [v for v in versions if v.status == status]
        
        if not versions:
            return None
        
        # Return the most recent version
        return max(versions, key=lambda x: x.created_at)
    
    def update_version_status(self, version_id: str, new_status: ContentStatus) -> bool:
        """
        Update the status of a version
        
        Args:
            version_id: ID of the version to update
            new_status: New status to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the existing version
            version = self.get_version(version_id)
            if not version:
                logger.error(f"Version {version_id} not found for status update")
                return False
            
            # Update the version
            version.status = new_status
            
            # Delete the old entry and add the updated one
            self.collection.delete(ids=[version_id])
            return self.save_version(version)
            
        except Exception as e:
            logger.error(f"Error updating version {version_id} status: {str(e)}")
            return False
    
    def delete_version(self, version_id: str) -> bool:
        """
        Delete a version from the database
        
        Args:
            version_id: ID of the version to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.collection.delete(ids=[version_id])
            logger.info(f"Deleted version {version_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting version {version_id}: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with statistics
        """
        try:
            result = self.collection.get()
            total_versions = len(result['documents'])
            
            # Count by status
            status_counts = {}
            agent_counts = {}
            chapter_counts = {}
            
            for metadata in result['metadatas']:
                status = metadata.get('status', 'unknown')
                agent = metadata.get('agent_type', 'unknown')
                chapter = metadata.get('chapter_id', 'unknown')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
                chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1
            
            return {
                'total_versions': total_versions,
                'status_distribution': status_counts,
                'agent_distribution': agent_counts,
                'chapter_distribution': chapter_counts,
                'database_path': self.db_path
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {}