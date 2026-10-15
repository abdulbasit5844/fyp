// Shapes documents for API responses: exposes `id`, hides `_id`, `__v`,
// and any path marked `private: true` in the schema.
function toJSONPlugin(schema) {
  const privatePaths = Object.keys(schema.paths).filter((p) => schema.paths[p].options.private);

  schema.set('toJSON', {
    virtuals: true,
    versionKey: false,
    transform(doc, ret) {
      ret.id = ret._id?.toString();
      delete ret._id;
      for (const p of privatePaths) delete ret[p];
      return ret;
    },
  });
}

module.exports = toJSONPlugin;
