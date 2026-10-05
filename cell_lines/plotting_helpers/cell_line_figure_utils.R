# Shared helpers for the metadata figure panels: data prep and the anatogram body.
# Colours and themes are in the repo-level themes.R; cancer type categories are in cancer_type_categories.yaml and cell line
# display names in cell_line_display_names.csv (both next to this file). Paths are relative to a notebook in cell_lines/notebooks/.
# The body comes from the gganatogram package (not on CRAN or conda-forge):
#   devtools::install_github("jespermaag/gganatogram")
suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(readr)
  library(ggplot2)
  library(gganatogram)
})
source(file.path("..", "..", "themes.R"))   # repo-level themes.R: site colours and ggplot themes

# ---- child-proportioned body ----
# gganatogram only ships adult bodies, so its polygons (outline and organs) are reshaped to child proportions:
# head about 1/4.7 of body height instead of 1/7.5 (a toddler / preschooler), a lower crotch (shorter legs), a sturdier
# trunk with a rounder belly, and narrower hips and thighs. The organs keep their adult shapes, so this is a proportion
# change, not paediatric anatomy.
# Coordinates: y_down is the anatogram's own y (0 at the top of the head, about 195 at the feet).
child_body <- TRUE
body_centre_x <- 52.6
y_landmarks_adult <- c(0, 26, 30, 103, 195)   # head top, chin, shoulders, crotch, feet
y_landmarks_child <- c(0, 41.75, 47, 119.5, 195)
frame_scale <- 1.07    # width of the trunk and arms relative to the adult body (above 1 = sturdier)
belly_scale <- 1.1     # extra width of the belly, so the trunk is round like a child's (the adult outline has a waist)
hip_scale <- 0.78      # width of the hips and thighs relative to the frame (the adult hips are wide, a child's are not)
arm_zone_start <- 28   # distance from the midline (adult plot units) beyond which a point counts as the arm
head_scale <- y_landmarks_child[2] / y_landmarks_adult[2]

warp_xy <- function(x, y_down) {
  if (!child_body) return(list(x = x, y = y_down))
  dx <- x - body_centre_x
  # one width factor per height for the head, trunk and legs: the head is enlarged in x as well as y, fading into the trunk
  # across the neck and shoulders, with a rounder belly and then narrower hips and thighs
  torso_y <- approx(c(0, 25, 31, 48, 62, 80, 98, 112, 135, 195),
                    c(head_scale, head_scale, frame_scale, frame_scale * belly_scale, frame_scale * belly_scale,
                      frame_scale * belly_scale, frame_scale * hip_scale, frame_scale * hip_scale, frame_scale, frame_scale),
                    xout = y_down, rule = 2)$y
  # the arms get a constant width factor, blended in away from the body: if they followed the hip narrowing, the hands
  # (which hang at hip height) would be squeezed by a factor that changes quickly with height, which shears the wrists
  t <- pmin(pmax((abs(dx) - arm_zone_start) / 7, 0), 1)
  w_arm <- t * t * (3 - 2 * t) * approx(c(34, 48, 114, 128), c(0, 1, 1, 0), xout = y_down, rule = 2)$y
  list(x = body_centre_x + dx * ((1 - w_arm) * torso_y + w_arm * frame_scale),
       y = approx(y_landmarks_adult, y_landmarks_child, xout = y_down, rule = 2)$y)
}

child_anatogram <- function() {
  anatogram <- get_anatogram(anatogram = NULL, organism = "human", sex = "female")
  lapply(anatogram, function(d) {
    w <- warp_xy(d$x, d$y)
    d$x <- w$x
    d$y <- w$y
    d
  })
}

# x and y range of the (child) body outline in plot coordinates, for cropping a figure to the body
body_extent <- function() {
  outline <- child_anatogram()$outline
  list(xlim = range(outline$x, na.rm = TRUE), ylim = -rev(range(outline$y, na.rm = TRUE)))
}

# ---- tumor sites: organs to fill on the body, and where to point on it ----
# Plot coordinates of the anatogram: x runs left to right, y is negative going down (head near 0, feet near -195).
# Points below are given for the adult body and moved with warp_xy() so they follow the child proportions.
# Markers (halos, eyes) are drawn where an organ is tiny or missing from the anatogram.
site_info <- tibble::tribble(
  ~site,                    ~organs,                      ~side,   ~anchor_x, ~anchor_y,
  "Central nervous system", list("brain"),               "right",  53,        -6,
  "Eye",                    list(character(0)),          "right",  55.8,     -12.8,
  "Normal reference lines", list(c("colon", "lung")),    "right",  59.5,     -44.7,
  "Kidney",                 list("kidney"),              "right",  59.2,     -67.2,
  "Ovary",                  list("ovary"),               "right",  57.9,     -90.1,
  "Adrenal gland",          list("adrenal_gland"),       "right",  57.3,     -61.8,
  "Soft tissue",            list("skeletal_muscle"),     "right",  45.2,    -106.6,
  "Bone",                   list("bone"),                "right",  44.6,    -162.5
)
stopifnot("every site needs a colour in themes.R" = setequal(site_info$site, names(site_colors)))
site_info$colour <- unname(site_colors[site_info$site])
anchor_xy <- warp_xy(site_info$anchor_x, -site_info$anchor_y)
site_info$anchor_x <- anchor_xy$x
site_info$anchor_y <- -anchor_xy$y

halo_points <- tibble::tribble(
  ~site,           ~x,   ~y,
  "Adrenal gland", 47.1, -63.4,
  "Adrenal gland", 57.3, -61.8,
  "Ovary",         47.5, -90.1,
  "Ovary",         57.9, -90.1,
  "Eye",           49.4, -12.8,
  "Eye",           55.8, -12.8
)
halo_xy <- warp_xy(halo_points$x, -halo_points$y)
halo_points$x <- halo_xy$x
halo_points$y <- -halo_xy$y
eye_scale <- if (child_body) head_scale else 1

ellipse_df <- function(cx, cy, rx, ry, n = 40) {
  t <- seq(0, 2 * pi, length.out = n)
  data.frame(x = cx + rx * cos(t), y = cy + ry * sin(t))
}

# ---- data prep ----
# Flatten the categories file into one row per raw cancer_type: cancer_type, cancer_group, site
read_categories <- function(categories_file) {
  categories <- yaml::read_yaml(categories_file)
  bind_rows(lapply(categories$sites, function(s) {
    bind_rows(lapply(s$groups, function(g) {
      tibble(cancer_type = unlist(g$cancer_types), cancer_group = g$name, site = s$name)
    }))
  }))
}

prepare_cancer_type_data <- function(metadata_file, categories_file, names_file = file.path("..", "plotting_helpers", "cell_line_display_names.csv")) {
  metadata <- read_csv(metadata_file, col_types = cols(.default = col_character()))
  # U2-OS has one row per plate condition; count each cell line once
  cell_lines <- metadata %>% distinct(cell_line_key, .keep_all = TRUE)
  group_map <- read_categories(categories_file)
  cell_lines <- left_join(cell_lines, group_map, by = "cancer_type")
  # standardised names for display (editable in cell_line_display_names.csv)
  display_names <- read_csv(names_file, col_types = cols(.default = col_character()))
  cell_lines <- left_join(cell_lines, display_names, by = "cell_line")
  stopifnot("every cell line must have a display name" = !anyNA(cell_lines$display_name))
  unmapped <- cell_lines %>% filter(is.na(site)) %>% distinct(cancer_type)
  stopifnot("every cancer_type must be listed in the categories file" = nrow(unmapped) == 0)
  stopifnot("every site must be defined in site_info" = all(cell_lines$site %in% site_info$site))

  group_counts <- cell_lines %>% count(site, cancer_group, name = "n")
  site_counts <- group_counts %>%
    group_by(site) %>%
    summarise(n = sum(n), .groups = "drop") %>%
    arrange(site == "Normal reference lines", desc(n))
  group_counts <- group_counts %>%
    mutate(site = factor(site, levels = site_counts$site)) %>%
    arrange(site, desc(n), cancer_group)
  list(cell_lines = cell_lines, group_counts = group_counts, site_counts = site_counts)
}

# ---- body ----
draw_body <- function(sites = site_info$site) {
  present <- site_info %>% filter(site %in% sites)
  organ_sets <- lapply(present$organs, unlist)
  organs <- data.frame(
    organ = unlist(organ_sets),
    colour = rep(present$colour, lengths(organ_sets)),
    value = 1,
    stringsAsFactors = FALSE
  )
  gganatogram(data = organs, fillOutline = "#F4F4F4", organism = "human", sex = "female", fill = "colour",
              anatogram = child_anatogram()) +
    theme_void()
}

# Halos behind tiny organs and coloured eyes for the eye (there is no eye organ in the anatogram)
body_markers <- function(sites = site_info$site, halo_size = 8, halo_alpha = 0.4) {
  layers <- list()
  for (s in intersect(sites, unique(halo_points$site))) {
    pts <- halo_points %>% filter(site == s)
    colour <- site_colors[[s]]
    layers <- c(layers, list(geom_point(data = pts, aes(x, y), shape = 16, colour = colour,
                                        alpha = halo_alpha, size = halo_size, inherit.aes = FALSE)))
    if (s == "Eye") {
      for (i in seq_len(nrow(pts))) {
        layers <- c(layers, list(geom_polygon(data = ellipse_df(pts$x[i], pts$y[i], 2.1 * eye_scale, 1.1 * eye_scale),
                                              aes(x, y), fill = colour, colour = "black", linewidth = 0.25,
                                              inherit.aes = FALSE)))
      }
    }
  }
  layers
}
