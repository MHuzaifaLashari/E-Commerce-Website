/* Citadel Brands — website settings, managed with admin.html (open it in Chrome or Edge).
   Saving in the admin page rewrites this file; hand edits are fine but keep it valid JSON.
     stock     low: below this a size shows "Only N left"; tiers: quantities at or above a tier show as "500+"
     slides    homepage hero slides, in order (hidden: true keeps a slide without showing it)
     banners   homepage images by slot (data-slot in index.html) -> {src, alt}
     brands    brand page banners -> {hero, heroPos}
     products  per style -> {img: card photo, img2: photo on mouse-over, gallery: product page photos in order} */
window.CB_SITE_CONFIG={
  "stock": {
    "low": 24,
    "tiers": []
  },
  "slides": [
    {
      "layout": "right",
      "image": "assets/dark-theme/image-004.jpg",
      "focus": "32% 0%",
      "eyebrow": "Fresh Layers",
      "title": "The Varsity\nContrast Hoodie",
      "text": "A modern spin on a classic varsity look — contrast details built for layering.",
      "buttons": [
        {
          "label": "Check it out",
          "href": "#featured"
        },
        {
          "label": "All AWDis",
          "href": "brand.html?brand=awdis",
          "ghost": true
        }
      ]
    },
    {
      "layout": "wall",
      "light": true,
      "image": "assets/figma/hero-fleece-group.jpg",
      "imageWide": "assets/figma/hero-fleece-group-wide.jpg",
      "eyebrow": "New · Heavyweight Collection",
      "title": "Heavyweight\nFleece",
      "text": "Thick, brushed-back fleece built for real warmth — crews and hoods in everyday colours, made to decorate.",
      "buttons": [
        {
          "label": "Shop fleece",
          "href": "brand.html?brand=awdis&cat=fleece"
        },
        {
          "label": "Explore AWDis",
          "href": "brand.html?brand=awdis",
          "ghost": true
        }
      ]
    },
    {
      "layout": "right",
      "image": "assets/dark-theme/image-010.jpg",
      "focus": "42% 15%",
      "eyebrow": "Everyday Staples",
      "title": "Bold Colour.\nEveryday T.",
      "text": "Soft cotton comfort in fresh seasonal hues. Easy to wear, easy to decorate.",
      "buttons": [
        {
          "label": "Shop T-shirts",
          "href": "brand.html?brand=awdis&cat=tshirts"
        },
        {
          "label": "New arrivals",
          "href": "#featured",
          "ghost": true
        }
      ]
    },
    {
      "layout": "left",
      "video": "assets/videos/ATA_ATY.mp4",
      "image": "assets/videos/ATA_ATY-poster.jpg",
      "seconds": 10,
      "eyebrow": "AWDis · Cotton Collection",
      "title": "AWDis\nCotton T-Shirts",
      "text": "Soft, breathable everyday cotton in the colours you wear most — a relaxed fit for the whole crew, and a smooth canvas for print.",
      "buttons": [
        {
          "label": "Shop T-shirts",
          "href": "brand.html?brand=awdis&cat=tshirts"
        },
        {
          "label": "Explore AWDis",
          "href": "#brands",
          "ghost": true
        }
      ]
    }
  ],
  "banners": {
    "cat-polos": {
      "src": "assets/figma/category-polo-03102026-3.png"
    }
  },
  "brands": {},
  "products": {
    "ATA001": {
      "img": "assets/products/ata001/uk-3.jpg",
      "img2": "assets/products/ata001/earthy-green.jpg",
      "gallery": [
        "assets/products/ata001/uk-1.jpg",
        "assets/products/ata001/uk-2.jpg",
        "assets/products/ata001/uk-4.jpg",
        "assets/products/ata001/uk-5.jpg",
        "assets/products/ata001/uk-3.jpg",
        "assets/products/ata001/uk-6.jpg"
      ]
    },
    "JCA002": {
      "img": "assets/products/jca002/gallery-1.jpg",
      "img2": "assets/products/jca002/mint.jpg",
      "gallery": [
        "assets/products/jca002/gallery-1.jpg",
        "assets/products/jca002/uk-1.jpg",
        "assets/products/jca002/uk-2.jpg",
        "assets/products/jca002/uk-4.jpg",
        "assets/products/jca002/uk-3.jpg",
        "assets/products/jca002.jpg"
      ]
    },
    "WBA020": {
      "img": "assets/products/wba020/gallery-1.jpg",
      "img2": "assets/products/wba020/purple.jpg",
      "gallery": [
        "assets/products/wba020/gallery-1.jpg"
      ]
    },
    "WBA010": {
      "img": "assets/products/wba010/gallery-1.jpg",
      "img2": "assets/products/wba010/sand.jpg",
      "gallery": [
        "assets/products/wba010/gallery-1.jpg",
        "assets/figma/category-polos.png"
      ]
    },
    "WBY020": {
      "img": "assets/products/wby020/gallery-1.jpg",
      "img2": "assets/products/wby020/royal.jpg",
      "gallery": [
        "assets/products/wby020/gallery-1.jpg"
      ]
    }
  }
};
