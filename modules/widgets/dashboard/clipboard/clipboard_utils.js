.pragma library

function isUrl(text) {
    if (!text) return false;
    return /^https?:\/\/[^\s]+/.test(text.trim());
}

function getGoogleFaviconUrl(domain) {
    if (!domain) return "";
    return "https://www.google.com/s2/favicons?domain=" + encodeURIComponent(domain) + "&sz=64";
}

function getFaviconUrl(text) {
    if (!text) return "";
    try {
        return new URL(text.trim()).origin + "/favicon.ico";
    } catch (e) {
        return "";
    }
}

function getFaviconFallbackUrl(text) {
    if (!text) return "";
    try {
        return getGoogleFaviconUrl(new URL(text.trim()).hostname);
    } catch (e) {
        return "";
    }
}
