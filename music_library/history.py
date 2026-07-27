"""Histórico local de fontes e tentativas, preparado para análise operacional futura."""

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


RETRY_DAYS = 30
SENSITIVE = re.compile(r"(?i)(cookie|authorization|bearer|token|secret|password)\s*[:=]\s*[^\s;]+")
SENSITIVE_QUERY = {"cookie", "token", "access_token", "auth", "authorization", "key", "secret"}


def utc_now():
    return datetime.now(timezone.utc)


def sanitizar_mensagem(mensagem):
    texto = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s;]+", r"\1[redigido]", str(mensagem or ""))
    return SENSITIVE.sub("[redigido]", texto)[:500]


def sanitizar_url(url):
    partes = urlsplit(url.strip())
    query = [(chave, valor) for chave, valor in parse_qsl(partes.query, keep_blank_values=True) if chave.lower() not in SENSITIVE_QUERY]
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(query), ""))


def iso(valor):
    return valor.astimezone(timezone.utc).isoformat()


class HistoryStore:
    def __init__(self, database):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL, track TEXT NOT NULL, resolved_at TEXT, downloaded_url TEXT, video_id TEXT, downloaded_at TEXT, UNIQUE(artist, album, track));
            CREATE TABLE IF NOT EXISTS candidates (id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL REFERENCES tracks(id), url TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('CATALOGO_OFICIAL','MANUAL','BUSCA_MANUAL')), is_valid INTEGER NOT NULL DEFAULT 0, UNIQUE(track_id, url));
            CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id), attempted_at TEXT NOT NULL, result TEXT NOT NULL CHECK(result IN ('SUCESSO','FALHA','BLOQUEADA')), error_category TEXT NOT NULL, message TEXT NOT NULL, technical_message TEXT NOT NULL DEFAULT '', next_retry_at TEXT);
        """)
        for column in ("downloaded_url TEXT", "video_id TEXT", "downloaded_at TEXT"):
            try:
                self.connection.execute(f"ALTER TABLE tracks ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        try:
            self.connection.execute("ALTER TABLE attempts ADD COLUMN technical_message TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        self.connection.commit()

    def close(self):
        self.connection.close()

    def track_id(self, artist, album, track):
        self.connection.execute("INSERT OR IGNORE INTO tracks(artist, album, track) VALUES (?, ?, ?)", (artist, album, track))
        row = self.connection.execute("SELECT id FROM tracks WHERE artist=? AND album=? AND track=?", (artist, album, track)).fetchone()
        self.connection.commit()
        return row["id"]

    def add_candidate(self, artist, album, track, url, source="MANUAL"):
        track_id = self.track_id(artist, album, track)
        url = sanitizar_url(url)
        self.connection.execute("INSERT OR IGNORE INTO candidates(track_id, url, source) VALUES (?, ?, ?)", (track_id, url, source))
        self.connection.commit()
        return self.connection.execute("SELECT id, url, source FROM candidates WHERE track_id=? AND url=?", (track_id, url)).fetchone()["id"]

    def mark_official(self, candidate_id):
        self.connection.execute("UPDATE candidates SET source='CATALOGO_OFICIAL', is_valid=1 WHERE id=?", (candidate_id,))
        self.connection.commit()

    def record_download(self, artist, album, track, url, video_id=None, now=None):
        track_id = self.track_id(artist, album, track)
        self.connection.execute("UPDATE tracks SET downloaded_url=?, video_id=?, downloaded_at=? WHERE id=?", (sanitizar_url(url), video_id, iso(now or utc_now()), track_id))
        self.connection.commit()

    def can_attempt(self, candidate_id, now=None):
        now = now or utc_now()
        row = self.connection.execute("SELECT t.resolved_at, a.next_retry_at FROM candidates c JOIN tracks t ON t.id=c.track_id LEFT JOIN attempts a ON a.id=(SELECT id FROM attempts WHERE candidate_id=c.id ORDER BY id DESC LIMIT 1) WHERE c.id=?", (candidate_id,)).fetchone()
        if not row or row["resolved_at"]:
            return False
        return not row["next_retry_at"] or datetime.fromisoformat(row["next_retry_at"]) <= now

    def record_attempt(self, candidate_id, result, category="UNKNOWN", message="", now=None, technical_message=""):
        now = now or utc_now()
        if not self.can_attempt(candidate_id, now):
            result, category, message, next_retry = "BLOQUEADA", "UNKNOWN", "Tentativa bloqueada até a próxima data permitida.", self.connection.execute("SELECT next_retry_at FROM attempts WHERE candidate_id=? ORDER BY id DESC LIMIT 1", (candidate_id,)).fetchone()["next_retry_at"]
        else:
            next_retry = iso(now + timedelta(days=RETRY_DAYS)) if result == "FALHA" else None
        self.connection.execute("INSERT INTO attempts(candidate_id, attempted_at, result, error_category, message, technical_message, next_retry_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (candidate_id, iso(now), result, category, sanitizar_mensagem(message), sanitizar_mensagem(technical_message), next_retry))
        if result == "SUCESSO":
            self.connection.execute("UPDATE candidates SET is_valid=1 WHERE id=?", (candidate_id,))
            self.connection.execute("UPDATE tracks SET resolved_at=? WHERE id=(SELECT track_id FROM candidates WHERE id=?)", (iso(now), candidate_id))
        self.connection.commit()

    def sources(self, artist, album, track):
        return self.connection.execute("""SELECT c.id, c.url, c.source, c.is_valid, a.result, a.error_category, a.message, a.technical_message, a.next_retry_at FROM candidates c JOIN tracks t ON t.id=c.track_id LEFT JOIN attempts a ON a.id=(SELECT id FROM attempts WHERE candidate_id=c.id ORDER BY id DESC LIMIT 1) WHERE t.artist=? AND t.album=? AND t.track=? ORDER BY c.id""", (artist, album, track)).fetchall()

    def history(self, artist=None, album=None, track=None, category=None):
        clauses, values = [], []
        for column, value in (("t.artist", artist), ("t.album", album), ("t.track", track), ("a.error_category", category)):
            if value:
                clauses.append(f"{column}=?")
                values.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self.connection.execute("SELECT t.artist, t.album, t.track, c.url, c.source, a.attempted_at, a.result, a.error_category, a.message, a.technical_message, a.next_retry_at FROM attempts a JOIN candidates c ON c.id=a.candidate_id JOIN tracks t ON t.id=c.track_id" + where + " ORDER BY a.id DESC", values).fetchall()
