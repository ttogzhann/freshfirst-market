export const RECIPE_IMAGE_FALLBACK = "/recipe-images/fallback.webp";

export function recipeImageSource(source: string): string {
  const authored = /^original-authored:\/\/freshfirst\/catalog\/v1\/(ff-original-(\d{3}))$/.exec(
    source,
  );
  if (authored && Number(authored[2]) >= 1 && Number(authored[2]) <= 80) {
    return `/recipe-images/${authored[1]}.webp`;
  }
  if (/^https?:\/\//i.test(source) || /^\/(?!\/)/.test(source)) return source;
  return RECIPE_IMAGE_FALLBACK;
}
