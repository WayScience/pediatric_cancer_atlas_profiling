# Shared look for every metadata figure panel: site colors and ggplot themes.
# Tumor site categories (which cancer types belong to which site) live in cell_lines/plotting_helpers/cancer_type_categories.yaml.
suppressPackageStartupMessages(library(ggplot2))

# ---- tumor site palette ----
# Okabe-Ito color-blind-safe palette (Okabe & Ito 2008), one color per site. The yellow is darkened from
# #F0E442 so it is visible on white; normal reference lines are gray.
site_colors <- c(
  "Central nervous system" = "#0072B2",
  "Eye"                    = "#56B4E9",
  "Adrenal gland"          = "#E69F00",
  "Kidney"                 = "#009E73",
  "Ovary"                  = "#D6BC00",
  "Soft tissue"            = "#CC79A7",
  "Bone"                   = "#D55E00",
  "Normal reference lines" = "#8C8C8C"
)

# Shades of a color: mix toward white (lighten) or toward black (darken); amount 0-1, vectorised over colors
lighten <- function(col, amount) {
  n <- max(length(col), length(amount))
  m <- t(col2rgb(rep_len(col, n)))
  rgb(m + (255 - m) * rep_len(amount, n), maxColorValue = 255)
}
darken <- function(col, amount = 0.25) {
  n <- max(length(col), length(amount))
  m <- t(col2rgb(rep_len(col, n)))
  rgb(m * (1 - rep_len(amount, n)), maxColorValue = 255)
}

# Text drawn in a site color is darkened so the lighter colors stay legible on white
site_text_colors <- setNames(darken(site_colors), names(site_colors))

# ---- origin ----
# Origin is shown as a shade of the site color: primary lighter, metastasis darker, unknown a very pale tint
origin_levels <- c("Primary", "Metastasis", "Unknown")
origin_shade <- function(base, origin) {
  ifelse(origin == "Primary", lighten(base, 0.45),
         ifelse(origin == "Metastasis", darken(base, 0.3), lighten(base, 0.85)))
}

# ---- sex ----
# Female / male / unknown, independent of the site colors (Paul Tol light pink and light blue, near-black for unknown)
sex_levels <- c("Female", "Male", "Unknown")
sex_colors <- c("Female" = "#EE99AA", "Male" = "#77AADD", "Unknown" = "#444444")

# ---- plate conditions ----
# One color per condition, independent of the site colors: Standard (uncoated baseline) is neutral gray, and the
# coatings and their double PFA fixed versions take Paul Tol (2021) muted / vibrant colors, which are not among the
# Okabe-Ito site colors: Synthemax indigo, Synthemax w/ PFA purple, Laminin cyan, Laminin w/ PFA red.
plate_colors <- c(
  "Standard"                         = "#BBBBBB",
  "Synthemax"                        = "#332288",
  "Synthemax w/ double PFA fixation" = "#AA4499",
  "Laminin"                          = "#88CCEE",
  "Laminin w/ double PFA fixation"   = "#CC3311"
)

# ---- themes ----
theme_panel <- function(base_size = 9) {
  theme_minimal(base_size = base_size) +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_blank(),
      panel.grid.major.x = element_line(color = "gray90", linewidth = 0.3),
      axis.ticks = element_blank(),
      axis.title.y = element_blank(),
      axis.text.y = element_text(color = "black", size = base_size + 1),
      axis.text.x = element_text(color = "gray30"),
      axis.title.x = element_text(color = "gray20", margin = margin(t = 6)),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.text = element_text(size = base_size),
      plot.background = element_rect(fill = "white", color = NA),
      plot.margin = margin(10, 12, 8, 10)
    )
}

annotation_theme <- function(margin_pt = 4, caption_size = 19, caption_gap = 6) {
  theme(
    # the atlas label (labs(caption = ...)) is centered under the whole figure
    plot.caption = element_text(face = "bold", size = caption_size, hjust = 0.5, margin = margin(t = caption_gap)),
    plot.caption.position = "plot",
    plot.background = element_rect(fill = "white", color = NA),
    plot.margin = margin(margin_pt, margin_pt, margin_pt, margin_pt)
  )
}
