interface GenreInfo {
  language: string
  region: string
  flag: string
}

const GENRE_MAP: Record<string, GenreInfo> = {
  'mandopop': { language: 'chinese', region: '中国', flag: '🇨🇳' },
  'cantopop': { language: 'chinese', region: '中国香港', flag: '🇭🇰' },
  'c-pop': { language: 'chinese', region: '中国', flag: '🇨🇳' },
  'chinese': { language: 'chinese', region: '中国', flag: '🇨🇳' },
  'taiwan': { language: 'chinese', region: '中国台湾', flag: '🇹🇼' },
  'taiwan pop': { language: 'chinese', region: '中国台湾', flag: '🇹🇼' },
  'singaporean': { language: 'chinese', region: '新加坡', flag: '🇸🇬' },
  'k-pop': { language: 'korean', region: '韩国', flag: '🇰🇷' },
  'korean': { language: 'korean', region: '韩国', flag: '🇰🇷' },
  'k-rap': { language: 'korean', region: '韩国', flag: '🇰🇷' },
  'k-indie': { language: 'korean', region: '韩国', flag: '🇰🇷' },
  'k-r&b': { language: 'korean', region: '韩国', flag: '🇰🇷' },
  'k-ballad': { language: 'korean', region: '韩国', flag: '🇰🇷' },
  'j-pop': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'japanese': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'j-rock': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'j-indie': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'j-rap': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'anime': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'anison': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'vocaloid': { language: 'japanese', region: '日本', flag: '🇯🇵' },
  'pop': { language: 'english', region: '全球', flag: '🌍' },
  'dance pop': { language: 'english', region: '全球', flag: '🌍' },
  'art pop': { language: 'english', region: '全球', flag: '🌍' },
  'synth-pop': { language: 'english', region: '全球', flag: '🌍' },
  'electropop': { language: 'english', region: '全球', flag: '🌍' },
  'dream pop': { language: 'english', region: '全球', flag: '🌍' },
  'chamber pop': { language: 'english', region: '全球', flag: '🌍' },
  'bedroom pop': { language: 'english', region: '全球', flag: '🌍' },
  'alt-pop': { language: 'english', region: '全球', flag: '🌍' },
  'hyperpop': { language: 'english', region: '全球', flag: '🌍' },
  'rock': { language: 'english', region: '全球', flag: '🌍' },
  'classic rock': { language: 'english', region: '全球', flag: '🌍' },
  'hard rock': { language: 'english', region: '全球', flag: '🌍' },
  'soft rock': { language: 'english', region: '全球', flag: '🌍' },
  'pop rock': { language: 'english', region: '全球', flag: '🌍' },
  'indie rock': { language: 'english', region: '全球', flag: '🌍' },
  'alt-rock': { language: 'english', region: '全球', flag: '🌍' },
  'psychedelic rock': { language: 'english', region: '全球', flag: '🌍' },
  'garage rock': { language: 'english', region: '全球', flag: '🌍' },
  'post-rock': { language: 'english', region: '全球', flag: '🌍' },
  'hip hop': { language: 'english', region: '美国', flag: '🇺🇸' },
  'rap': { language: 'english', region: '美国', flag: '🇺🇸' },
  'trap': { language: 'english', region: '美国', flag: '🇺🇸' },
  'drill': { language: 'english', region: '美国', flag: '🇺🇸' },
  'boom bap': { language: 'english', region: '美国', flag: '🇺🇸' },
  'conscious hip hop': { language: 'english', region: '美国', flag: '🇺🇸' },
  'gangsta rap': { language: 'english', region: '美国', flag: '🇺🇸' },
  'southern hip hop': { language: 'english', region: '美国', flag: '🇺🇸' },
  'east coast hip hop': { language: 'english', region: '美国', flag: '🇺🇸' },
  'west coast hip hop': { language: 'english', region: '美国', flag: '🇺🇸' },
  'r&b': { language: 'english', region: '美国', flag: '🇺🇸' },
  'contemporary r&b': { language: 'english', region: '美国', flag: '🇺🇸' },
  'neo soul': { language: 'english', region: '美国', flag: '🇺🇸' },
  'alternative r&b': { language: 'english', region: '美国', flag: '🇺🇸' },
  'edm': { language: 'english', region: '全球', flag: '🌍' },
  'electronic': { language: 'english', region: '全球', flag: '🌍' },
  'house': { language: 'english', region: '全球', flag: '🌍' },
  'deep house': { language: 'english', region: '全球', flag: '🌍' },
  'techno': { language: 'english', region: '全球', flag: '🌍' },
  'trance': { language: 'english', region: '全球', flag: '🌍' },
  'dubstep': { language: 'english', region: '全球', flag: '🌍' },
  'ambient': { language: 'english', region: '全球', flag: '🌍' },
  'downtempo': { language: 'english', region: '全球', flag: '🌍' },
  'idm': { language: 'english', region: '全球', flag: '🌍' },
  'latin': { language: 'other', region: '拉美', flag: '🌎' },
  'reggaeton': { language: 'other', region: '拉美', flag: '🌎' },
  'latin pop': { language: 'other', region: '拉美', flag: '🌎' },
  'latin rock': { language: 'other', region: '拉美', flag: '🌎' },
  'latin hip hop': { language: 'other', region: '拉美', flag: '🌎' },
  'salsa': { language: 'other', region: '拉美', flag: '🌎' },
  'bachata': { language: 'other', region: '拉美', flag: '🌎' },
  'dembow': { language: 'other', region: '拉美', flag: '🌎' },
  'bossa nova': { language: 'other', region: '巴西', flag: '🇧🇷' },
  'samba': { language: 'other', region: '巴西', flag: '🇧🇷' },
  'mpb': { language: 'other', region: '巴西', flag: '🇧🇷' },
  'indie': { language: 'english', region: '全球', flag: '🌍' },
  'indie pop': { language: 'english', region: '全球', flag: '🌍' },
  'indie folk': { language: 'english', region: '全球', flag: '🌍' },
  'indie soul': { language: 'english', region: '全球', flag: '🌍' },
  'folk': { language: 'english', region: '全球', flag: '🌍' },
  'folk rock': { language: 'english', region: '全球', flag: '🌍' },
  'neo-folk': { language: 'english', region: '全球', flag: '🌍' },
  'classical': { language: 'instrumental', region: '全球', flag: '🎼' },
  'orchestral': { language: 'instrumental', region: '全球', flag: '🎼' },
  'opera': { language: 'instrumental', region: '全球', flag: '🎼' },
  'baroque': { language: 'instrumental', region: '全球', flag: '🎼' },
  'instrumental': { language: 'instrumental', region: '全球', flag: '🎼' },
  'lo-fi': { language: 'instrumental', region: '全球', flag: '🎼' },
  'post-rock instrumental': { language: 'instrumental', region: '全球', flag: '🎼' },
  'jazz': { language: 'instrumental', region: '美国', flag: '🇺🇸' },
  'bebop': { language: 'instrumental', region: '美国', flag: '🇺🇸' },
  'cool jazz': { language: 'instrumental', region: '美国', flag: '🇺🇸' },
  'fusion': { language: 'instrumental', region: '美国', flag: '🇺🇸' },
  'smooth jazz': { language: 'instrumental', region: '美国', flag: '🇺🇸' },
  'acid jazz': { language: 'instrumental', region: '美国', flag: '🇺🇸' },
  'soul': { language: 'english', region: '美国', flag: '🇺🇸' },
  'funk': { language: 'english', region: '美国', flag: '🇺🇸' },
  'motown': { language: 'english', region: '美国', flag: '🇺🇸' },
  'disco': { language: 'english', region: '美国', flag: '🇺🇸' },
  'country': { language: 'english', region: '美国', flag: '🇺🇸' },
  'country pop': { language: 'english', region: '美国', flag: '🇺🇸' },
  'country rock': { language: 'english', region: '美国', flag: '🇺🇸' },
  'outlaw country': { language: 'english', region: '美国', flag: '🇺🇸' },
  'alt-country': { language: 'english', region: '美国', flag: '🇺🇸' },
  'americana': { language: 'english', region: '美国', flag: '🇺🇸' },
  'bluegrass': { language: 'english', region: '美国', flag: '🇺🇸' },
  'metal': { language: 'english', region: '全球', flag: '🌍' },
  'heavy metal': { language: 'english', region: '全球', flag: '🌍' },
  'death metal': { language: 'english', region: '全球', flag: '🌍' },
  'black metal': { language: 'english', region: '全球', flag: '🌍' },
  'thrash metal': { language: 'english', region: '全球', flag: '🌍' },
  'power metal': { language: 'english', region: '全球', flag: '🌍' },
  'doom metal': { language: 'english', region: '全球', flag: '🌍' },
  'progressive metal': { language: 'english', region: '全球', flag: '🌍' },
  'nu metal': { language: 'english', region: '全球', flag: '🌍' },
  'metalcore': { language: 'english', region: '全球', flag: '🌍' },
  'punk': { language: 'english', region: '全球', flag: '🌍' },
  'pop punk': { language: 'english', region: '全球', flag: '🌍' },
  'hardcore punk': { language: 'english', region: '全球', flag: '🌍' },
  'emo': { language: 'english', region: '全球', flag: '🌍' },
  'post-punk': { language: 'english', region: '全球', flag: '🌍' },
  'alternative': { language: 'english', region: '全球', flag: '🌍' },
  'grunge': { language: 'english', region: '美国', flag: '🇺🇸' },
  'shoegaze': { language: 'english', region: '全球', flag: '🌍' },
  'new wave': { language: 'english', region: '全球', flag: '🌍' },
  'post-punk revival': { language: 'english', region: '全球', flag: '🌍' },
  'britpop': { language: 'english', region: '英国', flag: '🇬🇧' },
  'uk garage': { language: 'english', region: '英国', flag: '🇬🇧' },
  'grime': { language: 'english', region: '英国', flag: '🇬🇧' },
  'drum and bass': { language: 'english', region: '英国', flag: '🇬🇧' },
  'dub': { language: 'english', region: '英国', flag: '🇬🇧' },
  'reggae': { language: 'other', region: '牙买加', flag: '🇯🇲' },
  'dancehall': { language: 'other', region: '牙买加', flag: '🇯🇲' },
  'ska': { language: 'other', region: '牙买加', flag: '🇯🇲' },
  'afrobeats': { language: 'other', region: '非洲', flag: '🌍' },
  'afrobeat': { language: 'other', region: '非洲', flag: '🌍' },
  'afropop': { language: 'other', region: '非洲', flag: '🌍' },
  'highlife': { language: 'other', region: '非洲', flag: '🌍' },
  'gospel': { language: 'english', region: '美国', flag: '🇺🇸' },
  'christian': { language: 'english', region: '全球', flag: '🌍' },
  'worship': { language: 'english', region: '全球', flag: '🌍' },
  'blues': { language: 'english', region: '美国', flag: '🇺🇸' },
  'delta blues': { language: 'english', region: '美国', flag: '🇺🇸' },
  'chicago blues': { language: 'english', region: '美国', flag: '🇺🇸' },
  'french': { language: 'other', region: '法国', flag: '🇫🇷' },
  'chanson': { language: 'other', region: '法国', flag: '🇫🇷' },
  'french pop': { language: 'other', region: '法国', flag: '🇫🇷' },
  'german': { language: 'other', region: '德国', flag: '🇩🇪' },
  'schlager': { language: 'other', region: '德国', flag: '🇩🇪' },
  'italian': { language: 'other', region: '意大利', flag: '🇮🇹' },
  'italo disco': { language: 'other', region: '意大利', flag: '🇮🇹' },
  'spanish': { language: 'other', region: '西班牙', flag: '🇪🇸' },
  'flamenco': { language: 'other', region: '西班牙', flag: '🇪🇸' },
  'indian': { language: 'other', region: '印度', flag: '🇮🇳' },
  'bollywood': { language: 'other', region: '印度', flag: '🇮🇳' },
  'bhangra': { language: 'other', region: '印度', flag: '🇮🇳' },
  'carnatic': { language: 'other', region: '印度', flag: '🇮🇳' },
  'arabic': { language: 'other', region: '中东', flag: '🌍' },
  'rai': { language: 'other', region: '中东', flag: '🌍' },
  'turkish': { language: 'other', region: '土耳其', flag: '🇹🇷' },
  'nordic': { language: 'other', region: '北欧', flag: '🌍' },
  'swedish': { language: 'other', region: '瑞典', flag: '🇸🇪' },
  'russian': { language: 'other', region: '俄罗斯', flag: '🇷🇺' },
  'world': { language: 'other', region: '全球', flag: '🌍' },
  'world fusion': { language: 'other', region: '全球', flag: '🌍' },
}

const UNKNOWN_INFO: GenreInfo = { language: 'other', region: '未知', flag: '🌍' }

export function classifyGenre(genre: string): GenreInfo {
  const key = genre.toLowerCase().trim()
  return GENRE_MAP[key] ?? UNKNOWN_INFO
}

export function inferLanguageDist(genres: { name: string; play_share: number }[]): Record<string, number> {
  const dist: Record<string, number> = {
    chinese: 0,
    english: 0,
    korean: 0,
    japanese: 0,
    instrumental: 0,
    other: 0,
  }

  for (const g of genres) {
    const info = classifyGenre(g.name)
    dist[info.language] += g.play_share
  }

  const total = Object.values(dist).reduce((s, v) => s + v, 0)
  if (total > 0) {
    for (const key of Object.keys(dist)) {
      dist[key] = Math.round((dist[key] / total) * 1000) / 10
    }
    // Adjust rounding so total is ~100
    const rounded = Object.values(dist).reduce((s, v) => s + v, 0)
    const diff = Math.round(1000 - rounded * 10)
    if (diff !== 0 && Object.keys(dist).length > 0) {
      dist['other'] = Math.round((dist['other'] * 10 + diff) * 10) / 100
    }
  }

  return dist
}

export function inferRegionDist(genres: { name: string; play_share: number }[]): { region: string; flag: string; play_share: number }[] {
  const agg: Record<string, { region: string; flag: string; play_share: number }> = {}

  for (const g of genres) {
    const info = classifyGenre(g.name)
    const key = info.region
    if (!agg[key]) {
      agg[key] = { region: info.region, flag: info.flag, play_share: 0 }
    }
    agg[key].play_share += g.play_share
  }

  return Object.values(agg).sort((a, b) => b.play_share - a.play_share)
}
