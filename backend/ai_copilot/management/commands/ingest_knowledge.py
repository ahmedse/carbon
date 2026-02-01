"""
Management command for ingesting knowledge documents into ChromaDB.

Usage:
    python manage.py ingest_knowledge                    # Ingest all documents
    python manage.py ingest_knowledge --category ghg_protocol  # Specific category
    python manage.py ingest_knowledge --clear            # Clear before ingesting
    python manage.py ingest_knowledge --dry-run          # Preview without ingesting
    python manage.py ingest_knowledge --stats            # Show statistics only
    python manage.py ingest_knowledge --file path/to/doc.pdf  # Single file
"""
import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ai_copilot.services.document_loader import DocumentLoader
from ai_copilot.services.text_chunker import TextChunker
from ai_copilot.services.rag_engine import RAGEngine


class Command(BaseCommand):
    help = 'Ingest knowledge documents into ChromaDB for AI Copilot'
    
    # Default knowledge directory
    KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / 'knowledge'
    
    # Supported categories
    CATEGORIES = [
        'ghg_protocol',
        'emission_factors', 
        'regulations',
        'best_practices',
        'general'
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            choices=self.CATEGORIES,
            help='Ingest only documents from specific category'
        )
        parser.add_argument(
            '--file',
            type=str,
            help='Ingest a specific file (must provide full path)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing knowledge base before ingesting'
        )
        parser.add_argument(
            '--clear-category',
            type=str,
            choices=self.CATEGORIES,
            help='Clear only a specific category before ingesting'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be ingested without making changes'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show current knowledge base statistics and exit'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=1000,
            help='Target chunk size in characters (default: 1000)'
        )
        parser.add_argument(
            '--chunk-overlap',
            type=int,
            default=200,
            help='Overlap between chunks in characters (default: 200)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-ingestion of already ingested documents'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress information'
        )
    
    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        
        # Initialize RAG engine
        try:
            self.rag_engine = RAGEngine()
            self.document_loader = DocumentLoader()
            self.text_chunker = TextChunker(
                chunk_size=options['chunk_size'],
                chunk_overlap=options['chunk_overlap']
            )
        except Exception as e:
            raise CommandError(f"Failed to initialize services: {e}")
        
        # Stats-only mode
        if options['stats']:
            self.show_statistics()
            return
        
        # Clear operations
        if options['clear']:
            self.clear_knowledge_base()
        elif options.get('clear_category'):
            self.clear_category(options['clear_category'])
        
        # Ingest single file
        if options.get('file'):
            self.ingest_single_file(
                options['file'],
                options.get('category', 'general'),
                options['dry_run'],
                options['force']
            )
            return
        
        # Ingest from knowledge directory
        self.ingest_knowledge_directory(
            options.get('category'),
            options['dry_run'],
            options['force']
        )
        
        # Show final statistics
        if not options['dry_run']:
            self.show_statistics()
    
    def show_statistics(self):
        """Display current knowledge base statistics."""
        stats = self.rag_engine.get_statistics()
        
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("📊 Knowledge Base Statistics"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        if stats.get('error'):
            self.stdout.write(self.style.ERROR(f"Error: {stats['error']}"))
            return
        
        self.stdout.write(f"📁 Total Documents: {stats['total_documents']}")
        self.stdout.write(f"📄 Total Chunks: {stats['total_chunks']}")
        
        if stats['last_updated']:
            self.stdout.write(f"🕐 Last Updated: {stats['last_updated']}")
        
        if stats['categories']:
            self.stdout.write("\n📂 Categories:")
            for cat, count in sorted(stats['categories'].items()):
                self.stdout.write(f"   • {cat}: {count} chunks")
        
        if stats['sources'] and self.verbose:
            self.stdout.write("\n📋 Source Files:")
            for source in stats['sources'][:20]:  # Limit to first 20
                self.stdout.write(f"   • {source}")
            if len(stats['sources']) > 20:
                self.stdout.write(f"   ... and {len(stats['sources']) - 20} more")
        
        self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))
    
    def clear_knowledge_base(self):
        """Clear all documents from knowledge base."""
        self.stdout.write(self.style.WARNING("🗑️  Clearing entire knowledge base..."))
        count = self.rag_engine.clear_all()
        self.stdout.write(self.style.SUCCESS(f"✓ Deleted {count} chunks"))
    
    def clear_category(self, category: str):
        """Clear documents from a specific category."""
        self.stdout.write(self.style.WARNING(f"🗑️  Clearing category: {category}..."))
        count = self.rag_engine.delete_by_category(category)
        self.stdout.write(self.style.SUCCESS(f"✓ Deleted {count} chunks from {category}"))
    
    def ingest_single_file(self, file_path: str, category: str, dry_run: bool, force: bool):
        """Ingest a single file."""
        path = Path(file_path)
        
        if not path.exists():
            raise CommandError(f"File not found: {file_path}")
        
        if not path.suffix.lower() in DocumentLoader.SUPPORTED_EXTENSIONS:
            raise CommandError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported: {DocumentLoader.SUPPORTED_EXTENSIONS}"
            )
        
        self.stdout.write(f"\n📄 Processing: {path.name}")
        
        # Check if already ingested
        if not force and self.rag_engine.has_source(path.name):
            self.stdout.write(self.style.WARNING(
                f"   ⚠️  Already ingested. Use --force to re-ingest."
            ))
            return
        
        if dry_run:
            self.stdout.write(self.style.NOTICE(
                f"   [DRY RUN] Would ingest: {path.name} (category: {category})"
            ))
            
            # Still show preview
            try:
                doc = self.document_loader.load(str(path))
                content = doc['content']
                metadata = doc['metadata']
                chunks = self.text_chunker.chunk(content, metadata)
                self.stdout.write(f"   → Would create {len(chunks)} chunks")
                self.stdout.write(f"   → Total characters: {len(content)}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   Error loading: {e}"))
            return
        
        # Delete existing if force
        if force:
            self.rag_engine.delete_by_source(path.name)
        
        # Ingest
        try:
            doc = self.document_loader.load(str(path))
            content = doc['content']
            metadata = doc['metadata']
            metadata['category'] = category
            
            count = self.rag_engine.ingest_document(content, metadata)
            self.stdout.write(self.style.SUCCESS(f"   ✓ Ingested {count} chunks"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ✗ Error: {e}"))
    
    def ingest_knowledge_directory(self, category: str, dry_run: bool, force: bool):
        """Ingest documents from the knowledge directory."""
        knowledge_dir = self.KNOWLEDGE_DIR
        
        if not knowledge_dir.exists():
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Knowledge directory not found: {knowledge_dir}"
            ))
            self.stdout.write("   Creating directory structure...")
            
            # Create directory structure
            for cat in self.CATEGORIES:
                cat_dir = knowledge_dir / cat
                cat_dir.mkdir(parents=True, exist_ok=True)
            
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ Created: {knowledge_dir}"
            ))
            self.stdout.write("   Please add knowledge documents and run again.")
            return
        
        # Determine categories to process
        if category:
            categories_to_process = [category]
        else:
            categories_to_process = [
                cat for cat in self.CATEGORIES 
                if (knowledge_dir / cat).exists()
            ]
        
        if not categories_to_process:
            self.stdout.write(self.style.WARNING(
                "No category directories found. Please add documents to:"
            ))
            for cat in self.CATEGORIES:
                self.stdout.write(f"   • {knowledge_dir / cat}")
            return
        
        total_files = 0
        total_chunks = 0
        
        self.stdout.write(self.style.SUCCESS(
            f"\n🚀 Starting Knowledge Ingestion"
            + (" [DRY RUN]" if dry_run else "")
        ))
        self.stdout.write(f"   Source: {knowledge_dir}")
        self.stdout.write(f"   Categories: {', '.join(categories_to_process)}")
        self.stdout.write("")
        
        for cat in categories_to_process:
            cat_dir = knowledge_dir / cat
            
            if not cat_dir.exists():
                continue
            
            self.stdout.write(self.style.HTTP_INFO(f"\n📂 Category: {cat}"))
            
            # Get all supported files
            files = self.document_loader.get_file_list(str(cat_dir))
            
            if not files:
                self.stdout.write("   No documents found")
                continue
            
            for file_path in sorted(files):
                file_name = Path(file_path).name
                
                # Check if already ingested
                if not force and self.rag_engine.has_source(file_name):
                    if self.verbose:
                        self.stdout.write(f"   ⏭️  Skipping (exists): {file_name}")
                    continue
                
                if dry_run:
                    self.stdout.write(f"   📄 [DRY RUN] Would ingest: {file_name}")
                    try:
                        doc = self.document_loader.load(file_path)
                        content = doc['content']
                        metadata = doc['metadata']
                        chunks = self.text_chunker.chunk(content, metadata)
                        self.stdout.write(f"      → {len(chunks)} chunks, {len(content)} chars")
                        total_chunks += len(chunks)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"      Error: {e}"))
                else:
                    self.stdout.write(f"   📄 Ingesting: {file_name}")
                    
                    try:
                        # Delete if force
                        if force:
                            self.rag_engine.delete_by_source(file_name)
                        
                        # Load and ingest
                        doc = self.document_loader.load(file_path)
                        content = doc['content']
                        metadata = doc['metadata']
                        metadata['category'] = cat
                        
                        count = self.rag_engine.ingest_document(content, metadata)
                        total_chunks += count
                        
                        self.stdout.write(self.style.SUCCESS(f"      ✓ {count} chunks"))
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"      ✗ Error: {e}"))
                
                total_files += 1
        
        # Summary
        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.NOTICE(
                f"📊 DRY RUN Summary: Would ingest {total_files} files → {total_chunks} chunks"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Ingestion Complete: {total_files} files → {total_chunks} chunks"
            ))
