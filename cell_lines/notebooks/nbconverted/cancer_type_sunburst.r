suppressPackageStartupMessages(library(stringr))

source(file.path("..", "plotting_helpers", "cell_line_figure_utils.R"))

metadata_file <- file.path("..", "pccma_cell_line_metadata.csv")
categories_file <- file.path("..", "plotting_helpers", "cancer_type_categories.yaml")
output_dir <- "figures"
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

# one table of wedges per ring: a wedge for each combination of the grouping columns of ring k, laid out around the circle
# in proportion to the number of cell lines, with a gap of site_gap degrees between tissue sites
ring_table <- function(k, data, group_keys, sort_keys, site_order, site_gap, n_total) {
  data %>%
    group_by(across(all_of(group_keys[[k]]))) %>%
    summarize(w = sum(weight), .groups = "drop") %>%
    arrange(across(all_of(sort_keys[[k]]))) %>%
    mutate(ring = k, span = 360 - site_gap * length(site_order),
           start = (as.integer(site) - 0.5) * site_gap + span * (cumsum(w) - w) / n_total,
           end = start + span * w / n_total, mid = (start + end) / 2)
}

# text color that stays readable on a given fill
text_on <- function(fill) ifelse(colSums(col2rgb(fill) * c(0.299, 0.587, 0.114)) / 255 < 0.55, "white", "gray15")
radial <- function(df) {
  df %>%
    mutate(r = (r0 + r1) / 2, x = r * sin(mid * pi / 180), y = r * cos(mid * pi / 180),
           angle = { phi <- ((90 - mid + 180) %% 360) - 180; ifelse(abs(phi) > 90, phi + 180, phi) },
           color = text_on(fill))
}

# ---- text measurement (approximate Helvetica character widths in em) ----
upi <- 1.75   # plot units per inch: sets the text size relative to the rings
em_widths <- setNames(c(556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278,
                        556, 500, 722, 500, 500, 500,
                        667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611,
                        722, 667, 944, 667, 667, 611, 278, 333, 333, 584) / 1000,
                      c(letters, LETTERS, " ", "(", ")", "="))
char_em <- function(ch) { w <- unname(em_widths[ch]); w[is.na(w)] <- 0.556; w }   # digits and others: 0.556 em
em_units <- function(size_mm) size_mm * 2.845 / 72 * upi                           # one em in plot units
text_units <- function(label, size_mm, bold = FALSE) {                              # width of the longest line
  max(sapply(strsplit(label, "\n")[[1]], function(l) sum(char_em(strsplit(l, "")[[1]])))) *
    (if (bold) 1.06 else 1) * em_units(size_mm)
}

# text along a circle of radius r, centered on angle `mid` (degrees clockwise from 12 o'clock); in the bottom half
# the text runs against the clock so that it stays upright
curved_text <- function(label, r, mid = 0, size_mm = 3.9, bold = TRUE) {
  chars <- strsplit(label, "")[[1]]
  em <- em_units(size_mm)
  w <- char_em(chars) * (if (bold) 1.06 else 1) * em
  offset <- cumsum(w) - w / 2 - sum(w) / 2       # distance of each character's center from the middle of the text
  flip <- cos(mid * pi / 180) < 0
  theta <- mid + (if (flip) -offset else offset) / r * 180 / pi
  r_base <- if (flip) r + 0.36 * em else r - 0.36 * em   # baseline radius, so capital letters are centered on r
  data.frame(char = chars, x = r_base * sin(theta * pi / 180), y = r_base * cos(theta * pi / 180),
             angle = if (flip) 180 - theta else -theta)
}

# polygon of an annular sector (a wedge of a ring)
arc_polygon <- function(id, r0, r1, start, end, fill) {
  a <- seq(start, end, length.out = max(2, ceiling((end - start) / 2)) + 1) * pi / 180
  tibble(id = id, fill = fill, x = c(r1 * sin(a), r0 * sin(rev(a))), y = c(r1 * cos(a), r0 * cos(rev(a))))
}

atlas <- prepare_cancer_type_data(metadata_file, categories_file)
site_order <- atlas$site_counts$site
plate_levels <- names(plate_colors)

rows <- read_csv(metadata_file, col_types = cols(.default = col_character())) %>%
  left_join(atlas$cell_lines %>% select(cell_line_key, site), by = "cell_line_key") %>%
  group_by(cell_line_key) %>%
  mutate(weight = 1 / n()) %>%
  ungroup() %>%
  transmute(cell_line_key,
            site = factor(site, site_order),
            origin = factor(coalesce(origin, "Unknown"), origin_levels),
            subtype = coalesce(subtype, "Unknown"),
            plate = factor(plate_conditions, plate_levels),
            weight)
stopifnot("unknown plate condition" = !anyNA(rows$plate))
stopifnot("weights must add up to one per cell line" = abs(sum(rows$weight) - n_distinct(rows$cell_line_key)) < 1e-9)
n_cell_lines <- n_distinct(rows$cell_line_key)

# order subtypes within each site and origin by size, with "Unknown" last
subtype_rank <- rows %>%
  group_by(site, origin, subtype) %>%
  summarize(w = sum(weight), .groups = "drop") %>%
  group_by(site, origin) %>%
  arrange(subtype == "Unknown", desc(w), subtype, .by_group = TRUE) %>%
  mutate(subtype_rank = row_number()) %>%
  ungroup() %>%
  select(site, origin, subtype, subtype_rank)
rows <- left_join(rows, subtype_rank, by = c("site", "origin", "subtype"))

# one table per ring: a wedge for each combination of the columns up to that ring
group_keys <- list("site", c("site", "origin"), c("site", "origin", "subtype", "subtype_rank"),
                   c("site", "origin", "subtype", "subtype_rank", "plate"))
sort_keys <- list("site", c("site", "origin"), c("site", "origin", "subtype_rank"),
                  c("site", "origin", "subtype_rank", "plate"))
site_gap <- 2.6   # degrees of white space between tissue sites
rings <- lapply(1:4, ring_table, data = rows, group_keys = group_keys, sort_keys = sort_keys,
                site_order = site_order, site_gap = site_gap, n_total = n_cell_lines)
cat("cell lines:", n_cell_lines, "| wedges per ring:", paste(sapply(rings, nrow), collapse = ", "), "\n")
print(as.data.frame(rings[[3]] %>% filter(subtype != "Unknown") %>% select(site, origin, subtype, w)), row.names = FALSE)

rings[[1]] <- rings[[1]] %>% mutate(base = unname(site_colors[as.character(site)]), fill = base)
rings[[2]] <- rings[[2]] %>%
  mutate(base = unname(site_colors[as.character(site)]), fill = origin_shade(base, as.character(origin)))
rings[[3]] <- rings[[3]] %>%
  mutate(base = unname(site_colors[as.character(site)]),
         origin_fill = origin_shade(base, as.character(origin)),
         fill = origin_fill)   # a subtype wedge keeps the color of the origin wedge it sits in
rings[[4]] <- rings[[4]] %>%
  mutate(base = unname(site_colors[as.character(site)]), fill = unname(plate_colors[as.character(plate)]))

# ring radii (plot units)
ring_gap <- 0.5                                  # plot units between rings; also holds the curved ring names
ring_widths <- c(1.0, 1.1, 1.2, 0.8)
r_start <- 1.9                                   # inner radius of ring 1 (the hole is ring_gap smaller)
r_inner <- r_start + c(0, cumsum(ring_widths + ring_gap))[1:4]
r_edges <- lapply(1:4, function(k) c(r_inner[k], r_inner[k] + ring_widths[k]))
wedges <- bind_rows(lapply(1:4, function(k) rings[[k]] %>% mutate(r0 = r_edges[[k]][1], r1 = r_edges[[k]][2]))) %>%
  mutate(id = row_number())
r_out <- max(wedges$r1)

# polygon outline of each wedge
poly_data <- bind_rows(lapply(seq_len(nrow(wedges)), function(i) {
  w <- wedges[i, ]
  a <- seq(w$start, w$end, length.out = max(2, ceiling((w$end - w$start) / 2)) + 1) * pi / 180
  tibble(id = w$id, fill = w$fill,
         x = c(w$r1 * sin(a), w$r0 * sin(rev(a))), y = c(w$r1 * cos(a), w$r0 * cos(rev(a))))
}))

subtype_names <- c("MYCN/ID2 amplified" = "MYCN/ID2 amp")

origin_labels <- radial(wedges %>% filter(ring == 2) %>% mutate(label = as.character(origin)))
subtype_labels <- radial(wedges %>% filter(ring == 3) %>% mutate(label = recode(subtype, !!!subtype_names)))

# ---- ring names: in the gap just outside each ring, centered on 12 o'clock ----
ring_label_size <- 4.9                           # text size (mm): larger than the site names, so the rings are easy to identify
ring_names <- c("Tissue site", "Origin", "Subtype", "Plate condition")
ring_label_chars <- bind_rows(lapply(1:4, function(k) curved_text(ring_names[k], r_edges[[k]][2] + ring_gap / 2, 0, ring_label_size)))

# ---- thin band in the site color around the outside, carrying the tissue site names ----
band_width <- 0.46
band_r0 <- r_out + ring_gap
band_r1 <- band_r0 + band_width
band_r <- (band_r0 + band_r1) / 2
band_text_size <- 3.6
sites <- wedges %>%
  filter(ring == 1) %>%
  mutate(label = paste0(str_remove(site, " lines$"), " (n=", round(w), ")"),   # "Normal reference lines" -> "Normal reference"
         text_w = sapply(label, text_units, size_mm = band_text_size, bold = TRUE),
         arc_len = (end - start) * pi / 180 * band_r,
         inside = text_w + 0.3 <= arc_len)
band_poly <- bind_rows(lapply(seq_len(nrow(sites)), function(i)
  arc_polygon(1000 + i, band_r0, band_r1, sites$start[i], sites$end[i], sites$base[i])))
band_chars <- bind_rows(lapply(which(sites$inside), function(i)
  curved_text(sites$label[i], band_r, sites$mid[i], band_text_size) %>% mutate(color = text_on(sites$base[i]))))
# sites too narrow for their name: named just outside the band
site_labels <- sites %>%
  filter(!inside) %>%
  mutate(x = (band_r1 + 0.3) * sin(mid * pi / 180), y = (band_r1 + 0.3) * cos(mid * pi / 180),
         hjust = ifelse(x >= 0, 0, 1),
         color = unname(site_text_colors[as.character(site)]))
out_ext <- site_labels$x + ifelse(site_labels$hjust == 0, 1, -1) *
  sapply(site_labels$label, text_units, size_mm = 3.9, bold = TRUE)

# ---- key on the right of the rings: the plate condition colors ----
key_size <- 3.8        # text size (mm)
key_swatch <- 0.3      # swatches are squares
key_pad <- 0.18        # plot units of padding around each key row
key_lineheight <- 0.85 # spacing between the lines of a multi-line label
line_h <- em_units(key_size)
key_labels <- str_replace(names(plate_colors), " w/ double PFA fixation", "\nw/ double PFA\nfixation")
item_h <- key_pad + line_h * (key_lineheight * str_count(key_labels, "\n") + 1)
title_h <- key_pad + line_h
key_h <- title_h + sum(item_h)
key_titles <- data.frame(y = key_h / 2 - title_h / 2, label = "Plate condition")
key_items <- data.frame(y = key_h / 2 - title_h - cumsum(item_h) + item_h / 2, label = key_labels, fill = unname(plate_colors))

key_x <- max(c(band_r1, out_ext[site_labels$hjust == 0])) + 0.5
key_right <- key_x + max(text_units("Plate condition", key_size, bold = TRUE),
                         0.5 + sapply(key_labels, text_units, size_mm = key_size))

x_lim <- c(min(c(-band_r1, out_ext[site_labels$hjust == 1])) - 0.05, key_right + 0.05)
y_lim <- c(min(c(-band_r1, site_labels$y - 0.25)) - 0.05, max(c(band_r1, site_labels$y + 0.25)) + 0.05)
margin_pt <- 4
fig_width <- diff(x_lim) / upi + 2 * margin_pt / 72
fig_height <- diff(y_lim) / upi + 2 * margin_pt / 72

panel <- ggplot()
for (k in 1:4) {
  panel <- panel +
    geom_polygon(data = poly_data %>% filter(id %in% wedges$id[wedges$ring == k]), aes(x, y, group = id, fill = fill),
                 color = "white", linewidth = 0.35)
}
panel <- panel +
  geom_polygon(data = band_poly, aes(x, y, group = id, fill = fill), color = "white", linewidth = 0.35) +
  scale_fill_identity() +
  geom_text(data = origin_labels, aes(x, y, label = label, angle = angle, color = color), size = 2.5, fontface = "bold") +
  geom_text(data = subtype_labels, aes(x, y, label = label, angle = angle, color = color), size = 2.5) +
  geom_text(data = band_chars, aes(x, y, label = char, angle = angle, color = color), vjust = 0,
            size = band_text_size, fontface = "bold") +
  geom_text(data = site_labels, aes(x, y, label = label, hjust = hjust, color = color), size = 3.9, fontface = "bold") +
  geom_text(data = ring_label_chars, aes(x, y, label = char, angle = angle), vjust = 0, size = ring_label_size,
            fontface = "bold", color = "gray20") +
  annotate("text", x = 0, y = 0.72, label = "PCCMA", size = 7, fontface = "bold") +
  annotate("text", x = 0, y = -0.3, label = paste0("n = ", n_cell_lines, "\npediatric cancer\ncell lines"), size = 3.8,
           fontface = "bold", lineheight = 0.95) +
  scale_color_identity() +
  coord_fixed(xlim = x_lim, ylim = y_lim, expand = FALSE, clip = "off") +
  theme_void() +
  annotation_theme(margin_pt)

panel <- panel +
  geom_text(data = key_titles, aes(key_x, y, label = label), hjust = 0, size = key_size, fontface = "bold", color = "gray15") +
  geom_text(data = key_items, aes(key_x + 0.5, y, label = label), hjust = 0, size = key_size, color = "gray15",
            lineheight = key_lineheight) +
  geom_rect(data = key_items,
            aes(xmin = key_x, xmax = key_x + key_swatch, ymin = y - key_swatch / 2, ymax = y + key_swatch / 2, fill = fill),
            color = "gray50", linewidth = 0.2, inherit.aes = FALSE)

cat(sprintf("subtype labels: %d of %d wedges (%d unknown); site names inside the band: %d of %d\n",
            nrow(subtype_labels), sum(wedges$ring == 3), sum(subtype_labels$label == "Unknown"),
            sum(sites$inside), nrow(sites)))
options(repr.plot.width = fig_width, repr.plot.height = fig_height, repr.plot.res = 100)
cat(sprintf("figure size: %.2f x %.2f in\n", fig_width, fig_height))
panel

ggsave(file.path(output_dir, "cancer_type_sunburst.png"), panel, width = fig_width, height = fig_height, dpi = 300, bg = "white")
ggsave(file.path(output_dir, "cancer_type_sunburst.pdf"), panel, width = fig_width, height = fig_height)
list.files(output_dir, pattern = "cancer_type_sunburst")
