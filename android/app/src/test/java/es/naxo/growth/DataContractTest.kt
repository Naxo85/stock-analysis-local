package es.naxo.growth

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.time.Instant

class DataContractTest {
    @Test fun missingNumberIsNotZero() {
        assertNull(JSONObject("{\"price\":null}").num("price"))
        assertEquals(0.0, JSONObject("{\"day_change\":0}").num("day_change")!!, 0.0)
    }
    @Test fun dashboardRejectsIncompatibleContract() {
        assertThrows(IllegalArgumentException::class.java) { Dashboard(JSONObject("{\"schema_version\":2,\"stocks\":[]}")) }
    }
    @Test fun failedAttemptKeepsPublishedTimestamp() {
        val dashboard = Dashboard(JSONObject("""{"schema_version":1,"stocks":[{"symbol":"RKLB","analysis_status":"ok","analysis_at":"2026-09-29T10:00:00Z","last_attempt_status":"failed","last_attempt_at":"2026-09-30T10:00:00Z"}]}"""))
        assertEquals("2026-09-29T10:00:00Z",dashboard.stocks.first().str("analysis_at"))
        assertEquals("failed",dashboard.stocks.first().str("last_attempt_status"))
    }
    @Test fun zoneSignalRequiresRecentQuoteAndPositionForSale() {
        val now=Instant.parse("2026-10-01T14:32:00Z")
        val stock=JSONObject("""{"price":70.34,"quote_at":"2026-10-01T14:31:00Z","shots":0,"plan":{"entry":{"lower":70,"upper":70.6},"resistance":{"lower":79,"upper":81}}}""")
        val buy=zoneSignal(stock,"regular",1.0,now)
        assertEquals("buy",buy.kind)
        assertTrue(buy.live)
        assertEquals("Zona de compra · Entrada",buy.label)
        stock.put("price",80.0)
        assertEquals("none",zoneSignal(stock,"regular",1.0,now).kind)
        stock.put("shots",1)
        assertEquals("sell",zoneSignal(stock,"regular",1.0,now).kind)
        stock.put("quote_at","2026-10-01T14:00:00Z")
        val saved=zoneSignal(stock,"regular",1.0,now)
        assertEquals("sell",saved.kind)
        assertFalse(saved.live)
        assertTrue(saved.label.startsWith("Último precio"))
    }
}
