from __future__ import annotations
import logging
from queue import Queue
import time

from typing import Any, Optional

import sqlalchemy

from pysagax.common.loop import Loop
from pysagax.gnd.database import ComIntDatabase, UAVEntity


class CommAggregate(Loop):
    """Background process for connecting to the CoreService stream interface and receiving binary data from there"""

    def __init__(
        self,
        db: ComIntDatabase,
        *args,
        **kwargs,
    ) -> None:
        self._db: ComIntDatabase = db
        self._app: Optional[Any] = None
        Loop.__init__(self, *args, **kwargs)

    def __call__(
        self,
        *args,
        **kwargs,
    ) -> None:
        self._app = self._db.get_app_instance()
        return super()._call(*args, **kwargs)

    def _loop(self) -> None:
        assert self._app
        with self._app.app_context():
            all_uavs = UAVEntity.query.order_by(UAVEntity.uav_id.asc()).filter_by(active=True).all()
            for uav in all_uavs:
                uav.last_seen = sqlalchemy.func.now()
            self._db.commit()
            print(
                ", ".join(
                    f"{uav.uav_label} ({uav.uav_address})" or "None" for uav in all_uavs
                )
            )
        time.sleep(1)
        pass
