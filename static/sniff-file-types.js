(function (BP) {
  "use strict";

  /** Extension → short type label for Sniff results */
  const SNIFF_EXT_LABELS = {
    epub: "Ebook",
    mobi: "Ebook",
    azw: "Ebook",
    azw3: "Ebook",
    pdf: "Ebook",
    fb2: "Ebook",
    lit: "Ebook",
    prc: "Ebook",
    djvu: "Ebook",
    chm: "Ebook",
    rtf: "Doc",
    md: "Text",
    html: "Doc",
    htm: "Doc",
    cbz: "Comic",
    cbr: "Comic",
    cb7: "Comic",
    mkv: "Video",
    mp4: "Video",
    avi: "Video",
    m4v: "Video",
    wmv: "Video",
    mov: "Video",
    ts: "Video",
    m2ts: "Video",
    vob: "Video",
    webm: "Video",
    iso: "Disc",
    img: "Disc",
    mp3: "Audio",
    flac: "Audio",
    m4a: "Audio",
    ape: "Audio",
    ogg: "Audio",
    wav: "Audio",
    wma: "Audio",
    zip: "Archive",
    rar: "Archive",
    "7z": "Archive",
    tar: "Archive",
    gz: "Archive",
    tgz: "Archive",
    bz2: "Archive",
    xz: "Archive",
    srt: "Subtitle",
    ass: "Subtitle",
    sub: "Subtitle",
    ssa: "Subtitle",
    jpg: "Image",
    jpeg: "Image",
    png: "Image",
    gif: "Image",
    webp: "Image",
    exe: "App",
    msi: "App",
    apk: "App",
    dmg: "App",
    deb: "App",
    rpm: "App",
    doc: "Doc",
    docx: "Doc",
    rtf: "Doc",
    txt: "Text",
    nfo: "Info",
  };

  function sniffExtensionFromTitle(title) {
    const raw = String(title || "").trim();
    if (!raw) return "";
    const lower = raw.toLowerCase();
    if (lower.endsWith(".tar.gz") || lower.endsWith(".tgz")) return "gz";
    if (lower.endsWith(".tar.bz2")) return "bz2";
    if (lower.endsWith(".tar.xz")) return "xz";
    if (lower.endsWith(".tar")) return "tar";
    const matches = [...raw.matchAll(/\.([a-z0-9]{2,5})\b/gi)];
    if (!matches.length) return "";
    const last = matches[matches.length - 1][1].toLowerCase();
    const prev = matches.length > 1 ? matches[matches.length - 2][1].toLowerCase() : "";
    if (prev === "tar" && (last === "gz" || last === "bz2" || last === "xz")) return last;
    return last;
  }

  function sniffFileType(title) {
    const ext = sniffExtensionFromTitle(title);
    if (!ext) return { ext: "", label: "—", title: "No extension detected" };
    const label = SNIFF_EXT_LABELS[ext] || ext.toUpperCase();
    return { ext, label, title: "." + ext + (SNIFF_EXT_LABELS[ext] ? " · " + label : "") };
  }

  BP.sniffFileType = sniffFileType;
  BP.SNIFF_EXT_LABELS = SNIFF_EXT_LABELS;
})(window.BookPup || (window.BookPup = {}));