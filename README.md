
# Family Cookbook

This repository contains my family culinary cookbook.
We use the JSON-LD recipe format specified by schema.org.
The format has the following non-standard deviations:

* Ingredients that start with "## " denote the beginning
  of an ingredient group.  They do not contain a valid ingredient.
* Instructions that start with "🛈 " are notes.

Work todo:

* Update 'totalTime', 'prepTime', 'performTime', 'cookTime'
* Add 'cookingMethod'
* Add 'recipeCuisine'
* Add 'url'


## Resources


### Recipe data formats

* [Schema.org recipe format](https://schema.org/Recipe)
  * [Google](https://developers.google.com/search/docs/appearance/structured-data/recipe)
  * [json-ld](https://jsonld.com/recipe/) (recommended by Google over microformat)
  * Does not support ingredient grouping
    [#311](https://github.com/nextcloud/cookbook/issues/311)
    [#2738](https://github.com/schemaorg/schemaorg/pull/2738)
    [#882](https://github.com/schemaorg/schemaorg/issues/882)
    [#2628](https://github.com/schemaorg/schemaorg/issues/2628)
* [JSON-LD](https://www.w3.org/TR/json-ld/)
  with [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) durations
* [JSON](https://www.json.org/json-en.html)
* [hRecipe](https://microformats.org/wiki/hrecipe)
* [h-recipe](https://microformats.org/wiki/h-recipe)
* Open Recipe Format: 
  [GitHub](https://github.com/techhat/openrecipeformat)
  [docs](https://open-recipe-format.readthedocs.io/)


### Open source recipes

* https://github.com/fictivekin/openrecipes
  * [data](https://s3.amazonaws.com/openrecipes/20170107-061401-recipeitems.json.gz)


### Self-hosted recipe websites

* Recipe Sage [GitHub](https://github.com/julianpoy/RecipeSage) [hosted](https://recipesage.com/)
* Tandoor Recipes [GitHub](https://github.com/TandoorRecipes/recipes) [hosted](https://tandoor.dev/)
* Open Eats [GitHub](https://github.com/qgriffith-zz/OpenEats) [hosted](http://www.openeats.org/)
* [Wordpress](https://wordpress.com/)
  * [Tasty Recipes](https://www.wptasty.com/tasty-recipes)
  * [WP Recipe Maker](https://wordpress.org/plugins/wp-recipe-maker/)
  * [Zip Recipes](https://ziprecipes.net/)


### Nutrition

* USDA [Food Data Central](https://fdc.nal.usda.gov/)
* [Edamam](https://www.edamam.com/)
* [esha research](https://esha.com/)


### Recipe Sites

* [SimilarWeb top](https://www.similarweb.com/top-websites/food-and-drink/cooking-and-recipes/)
* [AllRecipes](https://www.allrecipes.com/)
