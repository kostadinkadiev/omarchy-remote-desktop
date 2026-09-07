// Used by QML and tested in Qt's JavaScript engine.
function localPath(url) {
    return decodeURIComponent(String(url).replace(/^file:\/\//, ""))
}

function decode(text) {
    if (typeof text !== "string" || text.length > 65536)
        return { ok: false, error: "The helper returned too much data." }
    try {
        var value = JSON.parse(text)
        if (!value || typeof value !== "object" || Array.isArray(value) || typeof value.ok !== "boolean")
            throw new Error("Invalid response")
        return value
    } catch (_) {
        return { ok: false, error: "Could not read the helper response. Try refreshing." }
    }
}

function active(state) {
    return ["Starting", "Ready", "Connected"].indexOf(state) !== -1
}

function label(address) {
    // Also safe for Qt controls whose internal Text is owned by Qt.
    return String(address || "").replace(/[<>&]/g, "").slice(0, 160)
}
