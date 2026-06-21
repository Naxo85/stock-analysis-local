/*
 * Snippet para Value_refresh_1m / recalcYPRICE2.
 *
 * Sustituye en YPRICE() el bloque "Último precio persistente
 * (diccionario único)" que usa LP_DICT_V1 + ScriptProperties por este bloque.
 */

  /* ---------- Último precio temporal por ticker ---------- */
  const lastPriceKey = `LP_${sym}`;

  if (price == null){
    const prev = cache.get(lastPriceKey);
    if (prev != null) return Number(prev);
    return null;
  }

  /* ---------- guarda caché temporal ---------- */
  cache.put(key, String(price), 60);              // precio fresco: 60 s
  cache.put(lastPriceKey, String(price), 21600);  // último precio temporal: 6 h

  return Number(price);

/*
 * Añade esta función al final del script y ejecútala una vez manualmente.
 */
function clearLegacyYpricePropertiesNow() {
  PropertiesService.getScriptProperties().deleteProperty('LP_DICT_V1');
  Logger.log('LP_DICT_V1 deleted');
}
