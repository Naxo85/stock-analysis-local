package es.naxo.growth

import android.app.Application
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

fun JSONObject.str(key: String): String = if (isNull(key)) "" else optString(key, "")
fun JSONObject.num(key: String): Double? = if (isNull(key)) null else optDouble(key).takeIf { it.isFinite() }
fun JSONObject.obj(key: String): JSONObject = optJSONObject(key) ?: JSONObject()
fun JSONObject.rows(key: String): List<JSONObject> = (optJSONArray(key) ?: JSONArray()).let { a -> (0 until a.length()).mapNotNull { a.optJSONObject(it) } }

data class Dashboard(val raw: JSONObject) {
    val stocks = raw.rows("stocks")
    val changes = raw.rows("changes")
    val news = raw.rows("news")
    val market = raw.obj("market")
    val asOf = raw.str("generated_at")
    val stale = raw.optBoolean("stale", false)
    val warnings: List<String> = raw.optJSONArray("warnings")?.let { a -> (0 until a.length()).map { a.optString(it) } } ?: emptyList()
    init { require(raw.optInt("schema_version") == 1 && raw.has("stocks")) { "Formato de datos no compatible." } }
}

class AccessStore(context: Context) {
    private val preferences = context.getSharedPreferences("growth_access", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("growth-access", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("growth-access", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun save(token: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        preferences.edit().putString("code", Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(encrypted, Base64.NO_WRAP)).apply()
    }
    fun read(): String? = runCatching {
        val parts = preferences.getString("code", null)?.split(':') ?: return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP))) }
        String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), Charsets.UTF_8)
    }.getOrNull()
    fun clear() { preferences.edit().clear().apply() }
}

class GrowthRepository(private val context: Context) {
    private val directory = File(context.filesDir, "published").apply { mkdirs() }
    private fun cache(name: String) = File(directory, "$name.json")
    fun cachedDashboard(): Dashboard? = runCatching { Dashboard(JSONObject(cache("dashboard").readText())) }.getOrNull()
        ?: if (BuildConfig.OFFLINE_EDITION) runCatching { Dashboard(JSONObject(context.assets.open("dashboard.json").bufferedReader().use { it.readText() })) }.getOrNull() else null
    fun cachedReport(symbol: String): JSONObject? = runCatching { JSONObject(cache("report-$symbol").readText()) }.getOrNull()
        ?: if (BuildConfig.OFFLINE_EDITION && symbol.matches(Regex("[A-Z0-9.-]{1,12}"))) runCatching { JSONObject(context.assets.open("reports/$symbol.json").bufferedReader().use { it.readText() }) }.getOrNull() else null
    private fun save(name: String, payload: JSONObject) {
        val temporary = File(directory, "$name.tmp")
        temporary.writeText(payload.toString())
        check(temporary.renameTo(cache(name))) { "No se pudo guardar la copia local." }
    }
    private suspend fun request(path: String, token: String): JSONObject = withContext(Dispatchers.IO) {
        val base = BuildConfig.API_BASE_URL.trimEnd('/')
        require(base.startsWith("https://")) { "La conexión al servicio aún no está configurada." }
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 20000
            connection.readTimeout = 110000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Accept", "application/json")
            val code = connection.responseCode
            if (code == 401) throw IllegalArgumentException("Código de acceso incorrecto o revocado.")
            if (code == 404) throw IllegalStateException("No hay un informe publicado disponible para esta empresa.")
            if (code != 200) throw IllegalStateException("El servicio no está disponible ahora ($code).")
            val bytes = connection.inputStream.use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    output.write(buffer, 0, read)
                    require(output.size() <= 8 * 1024 * 1024) { "La respuesta del servicio es demasiado grande." }
                }
                output.toByteArray()
            }
            require(bytes.size <= 8 * 1024 * 1024) { "La respuesta del servicio es demasiado grande." }
            JSONObject(String(bytes, Charsets.UTF_8))
        } finally { connection.disconnect() }
    }
    suspend fun dashboard(token: String): Dashboard {
        val payload = request("/v1/dashboard", token)
        val dashboard = Dashboard(payload)
        withContext(Dispatchers.IO) { save("dashboard", payload) }
        return dashboard
    }
    suspend fun report(symbol: String, token: String): JSONObject {
        require(symbol.matches(Regex("[A-Z0-9.-]{1,12}")))
        val result = request("/v1/reports/$symbol", token)
        require(result.str("symbol") == symbol && result.str("analysis_status") == "ok") { "Informe no válido." }
        withContext(Dispatchers.IO) { save("report-$symbol", result) }
        return result
    }
    fun clear() { directory.listFiles()?.forEach { it.delete() } }
}

class GrowthViewModel(application: Application) : AndroidViewModel(application) {
    private val access = AccessStore(application)
    private val repository = GrowthRepository(application)
    private var token = access.read()
    val localEdition = BuildConfig.OFFLINE_EDITION
    var connected by mutableStateOf(token != null || localEdition); private set
    var dashboard by mutableStateOf(if (connected) repository.cachedDashboard() else null); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var offline by mutableStateOf(dashboard != null); private set
    var report by mutableStateOf<JSONObject?>(null); private set
    var reportBusy by mutableStateOf(false); private set
    var reportError by mutableStateOf<String?>(null); private set
    var reportOffline by mutableStateOf(false); private set
    private var reportJob: kotlinx.coroutines.Job? = null
    private val settings = application.getSharedPreferences("growth_settings", Context.MODE_PRIVATE)
    var appearance by mutableStateOf(settings.getString("appearance", "system") ?: "system"); private set
    init { if (connected) refresh() }
    fun changeAppearance(value: String) { appearance = value; settings.edit().putString("appearance", value).apply() }
    fun connect(code: String) {
        if (busy) return
        busy = true; error = null
        viewModelScope.launch {
            try {
                val cleaned = code.trim()
                val fresh = repository.dashboard(cleaned)
                access.save(cleaned); token = cleaned; dashboard = fresh; connected = true; offline = fresh.stale
            } catch (e: Exception) { error = friendly(e) }
            finally { busy = false }
        }
    }
    fun refresh() {
        val current = token ?: return
        if (busy) return
        busy = true; error = null
        viewModelScope.launch {
            try { dashboard = repository.dashboard(current); offline = dashboard?.stale == true }
            catch (e: Exception) { offline = dashboard != null; error = friendly(e) }
            finally { busy = false }
        }
    }
    fun openReport(symbol: String) {
        reportJob?.cancel()
        report = repository.cachedReport(symbol); reportOffline = report != null; reportBusy = true; reportError = null
        if (localEdition) { reportBusy = false; return }
        val current = token ?: run { reportBusy = false; return }
        reportJob = viewModelScope.launch {
            try { report = repository.report(symbol, current); reportOffline = false }
            catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { reportError = friendly(e) }
            finally { reportBusy = false }
        }
    }
    fun disconnect() {
        reportJob?.cancel(); access.clear(); repository.clear(); token = null; dashboard = null; report = null; connected = false; error = null
    }
    private fun friendly(error: Exception): String = when (error) {
        is java.net.UnknownHostException, is java.net.SocketTimeoutException, is java.net.ConnectException -> "No se pudo conectar. Puedes consultar la última copia guardada."
        else -> error.message ?: "No se pudo actualizar. Inténtalo de nuevo."
    }
}
