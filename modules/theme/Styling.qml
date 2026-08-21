pragma Singleton
import QtQuick
import qs.config

QtObject {
    readonly property string defaultFont: Config.defaultFont

    function radius(offset) {
        return Config.roundness > 0 ? Math.max(Config.roundness + offset, 0) : 0;
    }

    function fontSize(offset) {
        return Math.max(Config.theme.fontSize + offset, 8);
    }

    function monoFontSize(offset) {
        return Math.max(Config.theme.monoFontSize + offset, 8);
    }

    // Standard radius for floating surfaces (popups, OSD, notifications).
    // Keeps every "floating" element visually consistent regardless of where
    // it is defined.
    function popupRadius() {
        return radius(8);
    }

    // Apply an alpha to an existing theme color without unpacking channels by
    // hand everywhere (e.g. Qt.rgba(Colors.overBackground.r, .g, .b, 0.2)).
    function tint(color, alpha) {
        return Qt.rgba(color.r, color.g, color.b, alpha);
    }

    // Consistent interaction feedback alphas used across every interactive
    // surface (buttons, app icons, list rows) so hover/press feel is uniform.
    readonly property real hoverAlpha: 0.12
    readonly property real pressAlpha: 0.24

    // Animation duration tiers — each surface picks the tier that matches its
    // purpose. Centralized here so the entire shell shares one timing system.
    // Tier guide:
    //   instant    → micro-feedback (hover tint, focus ring, press ripple)
    //   quick      → toggles, checkboxes, small UI responses
    //   standard   → popups, dropdowns, OSD, tooltips
    //   considered → panels, sidebars, modals
    //   cinematic  → shell startup, lockscreen, wallpaper crossfade
    readonly property int animInstant: Config.animInstant
    readonly property int animQuick: Config.animQuick
    readonly property int animStandard: Config.animStandard
    readonly property int animConsidered: Config.animConsidered
    readonly property int animCinematic: Config.animCinematic

    // Legacy alias — keeps the 482 existing `Config.theme.animDuration` sites
    // working without editing them all. New code should use the tier above.
    readonly property int animDuration: Config.animDuration

    // Canonical easings — centralized so motion "weight" is uniform.
    // Out for entrances, In for exits, InOut for state transitions.
    // Now driven by Config.theme.animEasing* strings (validated via
    // ConfigValidator enum); fallback to Cubic variants on unknown.
    function _easingFor(name, fallback) {
        switch (name) {
        case "OutCubic": return Easing.OutCubic;
        case "OutQuart": return Easing.OutQuart;
        case "OutQuad": return Easing.OutQuad;
        case "OutExpo": return Easing.OutExpo;
        case "InCubic": return Easing.InCubic;
        case "InQuart": return Easing.InQuart;
        case "InQuad": return Easing.InQuad;
        case "InExpo": return Easing.InExpo;
        case "InOutCubic": return Easing.InOutCubic;
        case "InOutQuart": return Easing.InOutQuart;
        case "InOutQuad": return Easing.InOutQuad;
        case "InOutExpo": return Easing.InOutExpo;
        case "Linear": return Easing.Linear;
        default: return fallback;
        }
    }
    readonly property int animEasing: _easingFor(Config.theme.animEasingOut, Easing.OutCubic)
    readonly property int animEasingOut: _easingFor(Config.theme.animEasingOut, Easing.OutCubic)
    readonly property int animEasingIn: _easingFor(Config.theme.animEasingIn, Easing.InCubic)
    readonly property int animEasingInOut: _easingFor(Config.theme.animEasingInOut, Easing.InOutCubic)

    function getStyledRectConfig(variant) {
        switch (variant) {
        case "transparent":
            // Internal variant: uses bg config but with opacity, border and radius forced to 0
            const bgConfig = Config.theme.srBg;
            return {
                gradient: bgConfig.gradient,
                gradientType: bgConfig.gradientType,
                gradientAngle: bgConfig.gradientAngle,
                gradientCenterX: bgConfig.gradientCenterX,
                gradientCenterY: bgConfig.gradientCenterY,
                halftoneDotMin: bgConfig.halftoneDotMin,
                halftoneDotMax: bgConfig.halftoneDotMax,
                halftoneStart: bgConfig.halftoneStart,
                halftoneEnd: bgConfig.halftoneEnd,
                halftoneDotColor: bgConfig.halftoneDotColor,
                halftoneBackgroundColor: bgConfig.halftoneBackgroundColor,
                itemColor: bgConfig.itemColor,
                opacity: 0,
                border: [bgConfig.border[0], 0],
                radius: 0
            };
        case "bg":
            return Config.theme.srBg;
        case "popup":
            return Config.theme.srPopup;
        case "internalbg":
            return Config.theme.srInternalBg;
        case "pane":
            return Config.theme.srPane;
        case "common":
            return Config.theme.srCommon;
        case "focus":
            return Config.theme.srFocus;
        case "primary":
            return Config.theme.srPrimary;
        case "primaryfocus":
            return Config.theme.srPrimaryFocus;
        case "overprimary":
            return Config.theme.srOverPrimary;
        case "secondary":
            return Config.theme.srSecondary;
        case "secondaryfocus":
            return Config.theme.srSecondaryFocus;
        case "oversecondary":
            return Config.theme.srOverSecondary;
        case "tertiary":
            return Config.theme.srTertiary;
        case "tertiaryfocus":
            return Config.theme.srTertiaryFocus;
        case "overtertiary":
            return Config.theme.srOverTertiary;
        case "error":
            return Config.theme.srError;
        case "errorfocus":
            return Config.theme.srErrorFocus;
        case "overerror":
            return Config.theme.srOverError;
        case "barbg":
            return Config.theme.srBarBg;
        default:
            return Config.theme.srCommon;
        }
    }

    function srItem(variant) {
        return Config.resolveColor(getStyledRectConfig(variant).itemColor);
    }
}
