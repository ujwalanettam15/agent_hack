import logging
from typing import Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

import config

logger = logging.getLogger(__name__)


class Neo4jService:
    def __init__(self):
        self.driver = None

    def connect(self):
        if not config.NEO4J_URI:
            logger.warning("NEO4J_URI not set — graph features disabled")
            return
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            )
            self.driver.verify_connectivity()
            logger.info("Connected to Neo4j")
        except (Neo4jError, ServiceUnavailable, Exception) as e:
            logger.error("Neo4j connection failed: %s", e)
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    @property
    def available(self) -> bool:
        return self.driver is not None

    # ── Graph Operations ─────────────────────────────────────

    def seed_demo_data(self):
        """Pre-populate graph with demo scenario."""
        if not self.available:
            return
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run("""
                MERGE (user:Person {name: 'Neel'})
                MERGE (comcast:Service {name: 'Comcast', type: 'internet', monthlyRate: 85})
                MERGE (planet:Service {name: 'Planet Fitness', type: 'gym', monthlyRate: 25})
                MERGE (user)-[:SUBSCRIBES_TO {since: '2023-01-15', status: 'active'}]->(comcast)
                MERGE (user)-[:SUBSCRIBES_TO {since: '2022-06-01', status: 'active'}]->(planet)
            """))
            logger.info("Demo data seeded")

    def update_service_rate(
        self, service_name: str, old_rate: float, new_rate: float, confirmation: str
    ) -> dict:
        if not self.available:
            return {"status": "neo4j_unavailable"}
        with self.driver.session() as session:
            result = session.execute_write(
                lambda tx: tx.run(
                    "MATCH (s:Service {name: $name}) "
                    "SET s.monthlyRate = $new_rate, s.previousRate = $old_rate "
                    "CREATE (n:Negotiation {"
                    "  confirmation: $conf, date: datetime(), "
                    "  oldRate: $old_rate, newRate: $new_rate, "
                    "  savings: $old_rate - $new_rate"
                    "}) "
                    "MERGE (s)<-[:NEGOTIATED]-(n) "
                    "RETURN s.name AS service, n.savings AS savings",
                    name=service_name,
                    old_rate=old_rate,
                    new_rate=new_rate,
                    conf=confirmation,
                ).single()
            )
            if result:
                return {"service": result["service"], "savings": result["savings"]}
            return {"status": "not_found"}

    def cancel_service(
        self, user_name: str, service_name: str, confirmation: str
    ) -> dict:
        if not self.available:
            return {"status": "neo4j_unavailable"}
        with self.driver.session() as session:
            result = session.execute_write(
                lambda tx: tx.run(
                    "MATCH (p:Person {name: $user})-[r:SUBSCRIBES_TO]->(s:Service {name: $service}) "
                    "SET r.status = 'cancelled', r.cancelledAt = datetime(), "
                    "    r.confirmation = $conf "
                    "RETURN p.name AS person, s.name AS service",
                    user=user_name,
                    service=service_name,
                    conf=confirmation,
                ).single()
            )
            if result:
                return {"person": result["person"], "service": result["service"]}
            return {"status": "not_found"}

    def add_entity(
        self, entity_type: str, value: str, context: str, call_id: Optional[str] = None
    ) -> dict:
        if not self.available:
            return {"status": "neo4j_unavailable"}
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "MERGE (e:Entity {value: $value, type: $type}) "
                    "SET e.context = $context, e.extractedAt = datetime() "
                    "RETURN e.value AS value",
                    value=value,
                    type=entity_type,
                    context=context,
                )
            )
            return {"entity": value, "type": entity_type}

    def update_status(self, service_name: str, details: str) -> dict:
        if not self.available:
            return {"status": "neo4j_unavailable"}
        with self.driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    "MATCH (s:Service {name: $name}) "
                    "SET s.lastUpdate = datetime(), s.details = $details "
                    "RETURN s.name AS service",
                    name=service_name,
                    details=details,
                )
            )
            return {"service": service_name, "updated": True}


# Singleton
neo4j_service = Neo4jService()
