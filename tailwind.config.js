/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  // Indica onde estão seus arquivos HTML/JS para o Tailwind saber quais classes gerar
  content: [
    "./src/templates/**/*.html",
    "./src/static/js/**/*.js"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif']
      },
      colors: {
        lockton: {
          blue: '#00529B',
          dark: '#000000',
          gray: '#546E7A'
        }
      }
    },
  },
  plugins: [],
}