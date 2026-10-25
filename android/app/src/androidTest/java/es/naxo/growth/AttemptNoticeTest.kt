package es.naxo.growth

import android.graphics.Bitmap
import androidx.compose.material3.Surface
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import java.io.File

class AttemptNoticeTest {
    @get:Rule val compose = createComposeRule()
    private val financialAt = "2026-10-16T16:00:00Z"
    private val notice = "El último intento falló (2026-10-18T10:00:00Z). Se conserva el último informe válido con su fecha original."
    private val firstNotice = "El último intento falló (2026-10-18T10:00:00Z). Todavía no hay un informe válido disponible."
    private fun data(hasReport: Boolean, failed: Boolean = true): Dashboard {
        val stock = JSONObject().put("symbol", "TEST").put("group", "Prueba local")
            .put("analysis_status", if (hasReport) "ok" else "unavailable")
            .put("last_attempt_status", if (failed) "failed" else "ok")
            .put("analysis_at", if (hasReport) financialAt else JSONObject.NULL)
            .put("last_attempt_at", "2026-10-18T10:00:00Z")
            .put("attempt_notice", if (failed) (if (hasReport) notice else firstNotice) else "")
            .put("decision", if (hasReport) JSONObject().put("thesis_score", 7.0).put("setup_score", 6.0).put("narrative", "Informe anterior conservado.") else JSONObject())
            .put("plan", JSONObject())
        return Dashboard(JSONObject().put("schema_version", 1).put("generated_at", "2026-10-18T10:00:00Z").put("stocks", org.json.JSONArray().put(stock)))
    }
    @Test fun failedAttemptPreservesReportDateAndAccess() {
        compose.setContent { GrowthTheme(false) { Surface { ReportsScreen(data(true)) {} } } }
        compose.onAllNodesWithText("TEST")[0].performClick()
        compose.onNodeWithText(notice).performScrollTo().assertIsDisplayed()
        compose.onNodeWithText(dateTime(financialAt)).assertIsDisplayed()
        compose.onNodeWithText("Leer informe completo").assertIsEnabled()
        screenshot("attempt-failed-with-report")
    }
    @Test fun firstFailureShowsNoticeWithoutInventingReport() {
        compose.setContent { GrowthTheme(false) { Surface { ReportsScreen(data(false)) {} } } }
        compose.onAllNodesWithText("TEST")[0].performClick()
        compose.onNodeWithText(firstNotice).performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Leer informe completo").assertIsNotEnabled()
        compose.onNodeWithText(dateTime(financialAt)).assertDoesNotExist()
        screenshot("attempt-failed-without-report")
    }
    @Test fun tableShowsAttemptSeparatelyFromFinancialDate() {
        compose.setContent { GrowthTheme(false) { Surface { TableScreen(data(true)) {} } } }
        compose.onAllNodesWithText("TEST")[0].performClick()
        compose.onNodeWithText(notice).performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Análisis " + dateTime(financialAt)).assertIsDisplayed()
        screenshot("attempt-table-preserved-date")
    }
    @Test fun successfulAttemptDoesNotShowFailure() {
        compose.setContent { GrowthTheme(false) { Surface { ReportsScreen(data(true, false)) {} } } }
        compose.onAllNodesWithText("TEST")[0].performClick()
        compose.onNodeWithText(notice).assertDoesNotExist()
        compose.onNodeWithText("Leer informe completo").assertIsEnabled()
        screenshot("attempt-success-control")
    }
    private fun screenshot(name: String) {
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val directory = File(instrumentation.targetContext.getExternalFilesDir(null), "screenshots").apply { mkdirs() }
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        File(directory, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
