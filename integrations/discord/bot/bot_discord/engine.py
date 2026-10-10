"""Orquestación del transporte; el procesador es una dependencia de Fabián."""
import asyncio
from copy import deepcopy
import json

from .contracts import validate_source, validate_decision, delivery, snowflake


class Engine:
    def __init__(self, config, store, processor, transport):
        self.config, self.store = config, store
        self.processor, self.transport = processor, transport

    async def submit(self, event):
        source = validate_source(event, self.config)
        return await asyncio.to_thread(self.store.enqueue, source)

    async def step(self):
        job = await asyncio.to_thread(self.store.claim)
        if job is None:
            return False
        key = job["key"]
        source = json.loads(job["source"])
        if job["status"] == "queued":
            try:
                validate_source(source, self.config)
                result = await asyncio.wait_for(self.processor(deepcopy(source)), self.config.processor_timeout)
                decision = validate_decision(result, source)
            except Exception:
                await asyncio.to_thread(self.store.transition, key, "processing", "failed_processing", error="processor_or_contract")
                return True
            # Persistir resultado antes de planificar cualquier envío.
            await asyncio.to_thread(self.store.transition, key, "processing", "ready", decision=decision)
            return True
        try:
            plan = delivery(source, json.loads(job["decision"]), self.config)
            if plan is None:
                await asyncio.to_thread(self.store.transition, key, "checking", "recorded")
                return True
            # Cualquier fallo previo a send es reintentable explícitamente.
            channel = await self.transport.prepare(plan)
        except Exception:
            await asyncio.to_thread(self.store.transition, key, "checking", "blocked_delivery", error="destination_or_permissions")
            return True
        await asyncio.to_thread(self.store.transition, key, "checking", "sending")
        try:
            receipt = await self.transport.send(channel, plan, source)
            snowflake(receipt)
            await asyncio.to_thread(self.store.transition, key, "sending", "sent", receipt=receipt)
        except asyncio.CancelledError:
            # sending permanece visible tras una interrupción; nunca se reintenta.
            raise
        except Exception:
            await asyncio.to_thread(self.store.transition, key, "sending", "uncertain", error="send_outcome_unknown")
        return True
