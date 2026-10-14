import os
import re
import sqlite3
from datetime import datetime


class MemoryStore:
    """
    Local persistent memory for AethraOS.

    Memories are stored in a SQLite database.
    The user controls what is saved and forgotten.
    """

    def __init__(self, database_path=None):

        if database_path is None:
            project_root = os.getcwd()

            data_directory = os.path.join(
                project_root,
                "data"
            )

            os.makedirs(
                data_directory,
                exist_ok=True
            )

            database_path = os.path.join(
                data_directory,
                "aethra_memory.db"
            )

        self.database_path = database_path

        self._initialise_database()

    # ---------------------------------------------------------
    # DATABASE
    # ---------------------------------------------------------

    def _connect(self):

        return sqlite3.connect(
            self.database_path
        )

    def _initialise_database(self):

        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            """)

            connection.commit()

    # ---------------------------------------------------------
    # SAVE MEMORY
    # ---------------------------------------------------------

    def remember(self, content):

        content = str(content).strip()

        if not content:
            return {
                "success": False,
                "message": "Memory cannot be empty."
            }

        if len(content) > 1000:
            return {
                "success": False,
                "message": (
                    "That memory is too long. "
                    "Please keep it under 1000 characters."
                )
            }

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        try:

            with self._connect() as connection:

                connection.execute(
                    """
                    INSERT INTO memories (content, created_at)
                    VALUES (?, ?)
                    """,
                    (content, created_at)
                )

                connection.commit()

            return {
                "success": True,
                "message": "Memory saved.",
                "content": content
            }

        except sqlite3.IntegrityError:

            return {
                "success": True,
                "message": "I already remember that.",
                "content": content
            }

        except sqlite3.Error as exc:

            return {
                "success": False,
                "message": f"Database error: {exc}"
            }

    # ---------------------------------------------------------
    # GET ALL MEMORIES
    # ---------------------------------------------------------

    def get_all(self):

        try:

            with self._connect() as connection:

                rows = connection.execute(
                    """
                    SELECT id, content, created_at
                    FROM memories
                    ORDER BY id DESC
                    """
                ).fetchall()

            return [
                {
                    "id": row[0],
                    "content": row[1],
                    "created_at": row[2]
                }
                for row in rows
            ]

        except sqlite3.Error:
            return []

    # ---------------------------------------------------------
    # SEARCH MEMORIES
    # ---------------------------------------------------------

    def search(self, query, limit=5):
        """
        Semantic-style memory search using TF-IDF + cosine similarity.

        Falls back gracefully if numpy is unavailable.
        No external embedding APIs are used.
        """
        query = str(query).strip()
        if not query:
            return []

        memories = self.get_all()
        if not memories:
            return []

        try:
            import math
            from collections import Counter

            # Tokenise
            docs = [self._tokens(m["content"]) for m in memories]
            query_tokens = self._tokens(query)

            if not query_tokens:
                return []

            # Build vocabulary
            vocab = set(query_tokens)
            for doc in docs:
                vocab.update(doc)
            vocab = sorted(vocab)
            if not vocab:
                return []

            index = {term: i for i, term in enumerate(vocab)}
            n_docs = len(docs)
            dim = len(vocab)

            # Document frequency
            df = Counter()
            for doc in docs:
                for term in set(doc):
                    df[term] += 1

            def tfidf_vector(tokens):
                counts = Counter(tokens)
                total = sum(counts.values()) or 1
                vec = [0.0] * dim
                for term, count in counts.items():
                    if term not in index:
                        continue
                    tf = count / total
                    # Smoothed IDF
                    idf = math.log((n_docs + 1) / (df.get(term, 0) + 1)) + 1.0
                    vec[index[term]] = tf * idf
                return vec

            def cosine(a, b):
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(x * x for x in b))
                if na == 0 or nb == 0:
                    return 0.0
                return dot / (na * nb)

            q_vec = tfidf_vector(query_tokens)
            scored = []
            for memory, tokens in zip(memories, docs):
                if not tokens:
                    continue
                score = cosine(q_vec, tfidf_vector(tokens))
                if score > 0.05:  # small threshold to drop noise
                    scored.append((score, memory))

            scored.sort(key=lambda item: item[0], reverse=True)
            return [memory for score, memory in scored[:limit]]

        except Exception:
            # Fallback to original word-overlap behaviour
            query_words = self._words(query)
            if not query_words:
                return []

            scored_memories = []
            for memory in memories:
                memory_words = self._words(memory["content"])
                overlap = query_words.intersection(memory_words)
                if not overlap:
                    continue
                score = len(overlap) / max(len(query_words), 1)
                scored_memories.append((score, memory))

            scored_memories.sort(key=lambda item: item[0], reverse=True)
            return [memory for score, memory in scored_memories[:limit]]

    # ---------------------------------------------------------
    # FORGET A MEMORY
    # ---------------------------------------------------------

    def forget(self, phrase):

        phrase = str(phrase).strip()

        if not phrase:
            return {
                "success": False,
                "message": "Please specify what to forget."
            }

        try:

            with self._connect() as connection:

                cursor = connection.execute(
                    """
                    DELETE FROM memories
                    WHERE LOWER(content) = LOWER(?)
                    """,
                    (phrase,)
                )

                connection.commit()

                deleted_count = cursor.rowcount

            if deleted_count:

                return {
                    "success": True,
                    "message": "I have forgotten that memory."
                }

            # If there was no exact match, search for a
            # unique memory containing the supplied phrase.
            matches = self.search(
                phrase,
                limit=10
            )

            if len(matches) == 1:

                memory_id = matches[0]["id"]

                with self._connect() as connection:

                    connection.execute(
                        "DELETE FROM memories WHERE id = ?",
                        (memory_id,)
                    )

                    connection.commit()

                return {
                    "success": True,
                    "message": (
                        "I have forgotten the matching memory: "
                        + matches[0]["content"]
                    )
                }

            if len(matches) > 1:

                return {
                    "success": False,
                    "message": (
                        "I found multiple matching memories. "
                        "Please specify the exact memory you "
                        "want me to forget."
                    ),
                    "matches": [
                        item["content"]
                        for item in matches
                    ]
                }

            return {
                "success": False,
                "message": "I could not find that memory."
            }

        except sqlite3.Error as exc:

            return {
                "success": False,
                "message": f"Database error: {exc}"
            }

    # ---------------------------------------------------------
    # CLEAR ALL MEMORIES
    # ---------------------------------------------------------

    def clear_all(self):

        try:

            with self._connect() as connection:

                connection.execute(
                    "DELETE FROM memories"
                )

                connection.commit()

            return {
                "success": True,
                "message": "All saved memories have been deleted."
            }

        except sqlite3.Error as exc:

            return {
                "success": False,
                "message": f"Database error: {exc}"
            }

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _ignored_words():
        return {
            "a", "an", "the", "and", "or", "but",
            "is", "are", "was", "were", "be", "been",
            "i", "me", "my", "mine", "you", "your",
            "we", "our", "it", "its", "to", "of",
            "in", "on", "at", "for", "with", "that",
            "this", "about", "please", "remember",
            "forget", "what", "do", "does",
        }

    @staticmethod
    def _words(text):
        """Return a set of content words (used by forget fallback)."""
        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            str(text).lower()
        )
        ignored = MemoryStore._ignored_words()
        return {word for word in words if word not in ignored}

    @staticmethod
    def _tokens(text):
        """
        Return a list of content tokens for TF-IDF.
        Keeps multiplicity (unlike the set-based _words).
        """
        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            str(text).lower()
        )
        ignored = MemoryStore._ignored_words()
        return [word for word in words if word not in ignored]