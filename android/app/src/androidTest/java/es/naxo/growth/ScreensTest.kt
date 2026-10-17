package es.naxo.growth

import android.graphics.Bitmap
import androidx.compose.material3.Surface
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.performClick
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import java.io.File

class ScreensTest {
    @get:Rule val compose = createComposeRule()
    private val data = Dashboard(JSONObject("""{
      "schema_version":1,"generated_at":"2026-09-30T10:00:00Z",
      "market":{"risk_label":"Mixto 52/100","risk_score":52,"vxn":21.4,"vxn_label":"VXN: normal","qqq_day":0.008,"qqq_20d":0.039,"qqq_drawdown":-0.05,"quote_at":"2026-09-30T09:59:00Z","groups":[]},
      "stocks":[{"symbol":"RKLB","group":"Espacio","shots":1,"price":70.34,"day_change":0.012,"strength":7.2,"quote_at":"2026-09-30T09:59:00Z","analysis_at":"2026-09-29T17:17:00Z","analysis_status":"ok","last_attempt_status":"ok","decision":{"thesis_score":8.1,"setup_score":7.5,"narrative":"La tesis mantiene su trayectoria."},"plan":{"entry":{"lower":70,"upper":70.6},"ambitious_entry":{"lower":64.7,"upper":65.3},"resistance":{"lower":79.8,"upper":81.2},"entry_strength_score":82,"washout_strength_score":80,"resistance_strength_score":75}}],
      "changes":[{"id":"RKLB:1","symbol":"RKLB","kind":"catalyst","title":"Nuevo contrato de lanzamiento","detail":"Catalizador de prueba.","impact":8,"at":"2026-09-29T17:17:00Z"}],
      "news":[],"warnings":[]
    }"""))

    @Test fun homeAndEmptyNews() {
        compose.setContent { GrowthTheme(false) { Surface { HomeScreen(data) {} } } }
        compose.onNodeWithText("Mixto 52/100").assertIsDisplayed()
        screenshot("home-light")
    }
    @Test fun changesOpensSelectedReport() {
        var selected = ""
        compose.setContent { GrowthTheme(false) { Surface { ChangesScreen(data) { selected = it } } } }
        compose.onNodeWithText("Nuevo contrato de lanzamiento").performClick()
        assertEquals("", selected)
        compose.onNodeWithText("Catalizador de prueba.").assertIsDisplayed()
        compose.onNodeWithText("Leer informe completo").performClick()
        assertEquals("RKLB", selected)
        screenshot("changes-light")
    }
    @Test fun reportExpandsThenOpens() {
        var selected = ""
        compose.setContent { GrowthTheme(false) { Surface { ReportsScreen(data) { selected = it } } } }
        compose.onAllNodesWithText("RKLB")[0].performClick()
        compose.onNodeWithText("Leer informe completo").performClick()
        assertEquals("RKLB", selected)
        screenshot("reports-light")
    }
    @Test fun tableAndPortfolioFilter() {
        compose.setContent { GrowthTheme(false) { Surface { TableScreen(data) {} } } }
        compose.onNodeWithText("Cartera").performClick()
        compose.onNodeWithText("RKLB").assertIsDisplayed()
        compose.onNodeWithText("RKLB").performClick()
        compose.onNodeWithText("Leer informe completo").assertIsDisplayed()
        screenshot("table-light")
    }
    @Test fun tableDarkTheme() {
        compose.setContent { GrowthTheme(true) { Surface { TableScreen(data) {} } } }
        compose.onNodeWithText("RKLB").assertIsDisplayed()
        screenshot("table-dark")
    }
    private fun screenshot(name: String) {
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val directory = File(instrumentation.targetContext.getExternalFilesDir(null), "screenshots").apply { mkdirs() }
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        File(directory, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
