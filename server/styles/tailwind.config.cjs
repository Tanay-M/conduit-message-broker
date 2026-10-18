const path = require('node:path');

module.exports = {
  content: [
    path.join(__dirname, '../app/templates/**/*.html'),
    path.join(__dirname, '../app/static/app.js'),
    path.join(__dirname, '../app/static/workspace.js'),
  ],
  theme: { extend: {} },
  plugins: [],
};
