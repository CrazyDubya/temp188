// voter_matcher.cpp
#include "voter_matcher.hpp"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>

std::string VoterDatabase::normalizeString(const std::string& input) {
    std::string result;
    result.reserve(input.length());
    std::transform(input.begin(), input.end(), 
                  std::back_inserter(result), 
                  [](unsigned char c){ return std::toupper(c); });
    return result;
}

bool VoterDatabase::loadVoterData(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) return false;

    records.clear();
    nameIndex.clear();
    addressIndex.clear();

    std::string line;
    // Skip header
    std::getline(file, line);
    
    while (std::getline(file, line)) {
        std::stringstream ss(line);
        std::string field;
        std::vector<std::string> fields;
        
        while (std::getline(ss, field, ',')) {
            fields.push_back(field);
        }
        
        if (fields.size() >= 6) {
            auto record = std::make_shared<VoterRecord>();
            record->vsn = fields[0];
            record->party = fields[1];
            record->firstName = normalizeString(fields[2]);
            record->lastName = normalizeString(fields[3]);
            record->streetNumber = normalizeString(fields[4]);
            record->streetName = normalizeString(fields[5]);
            record->fullName = record->firstName + " " + record->lastName;
            record->fullAddress = record->streetNumber + " " + record->streetName;
            
            size_t idx = records.size();
            nameIndex[record->fullName].push_back(idx);
            addressIndex[record->fullAddress].push_back(idx);
            records.push_back(record);
        }
    }
    
    return true;
}

std::vector<SearchResult> VoterDatabase::findExactMatches(
    const std::string& fullName, 
    const std::string& fullAddress
) {
    std::vector<SearchResult> results;
    
    auto nameIt = nameIndex.find(fullName);
    auto addrIt = addressIndex.find(fullAddress);
    
    if (nameIt != nameIndex.end() && addrIt != addressIndex.end()) {
        std::vector<size_t> matches;
        std::set_intersection(
            nameIt->second.begin(), nameIt->second.end(),
            addrIt->second.begin(), addrIt->second.end(),
            std::back_inserter(matches)
        );
        
        for (size_t idx : matches) {
            SearchResult result;
            result.type = SearchResult::MatchType::EXACT;
            result.score = 100.0;
            result.record = records[idx];
            results.push_back(result);
        }
    }
    
    return results;
}

std::vector<SearchResult> VoterDatabase::findFuzzyMatches(
    const std::string& fullName,
    const std::string& fullAddress,
    double threshold
) {
    std::vector<SearchResult> results;
    
    for (size_t i = 0; i < records.size(); ++i) {
        const auto& record = records[i];
        
        double nameScore = rapidfuzz::fuzz::ratio(
            fullName, record->fullName
        );
        
        double addressScore = rapidfuzz::fuzz::ratio(
            fullAddress, record->fullAddress
        );
        
        if (nameScore >= threshold) {
            SearchResult result;
            result.type = SearchResult::MatchType::FUZZY_NAME;
            result.score = nameScore;
            result.record = record;
            results.push_back(result);
        }
        
        if (addressScore >= threshold) {
            SearchResult result;
            result.type = SearchResult::MatchType::FUZZY_ADDRESS;
            result.score = addressScore;
            result.record = record;
            results.push_back(result);
        }
    }
    
    return results;
}

std::vector<SearchResult> VoterDatabase::findMatches(
    const std::string& firstName,
    const std::string& lastName,
    const std::string& streetNumber,
    const std::string& streetName,
    double fuzzyThreshold
) {
    std::string normFirstName = normalizeString(firstName);
    std::string normLastName = normalizeString(lastName);
    std::string normStreetNum = normalizeString(streetNumber);
    std::string normStreetName = normalizeString(streetName);
    
    std::string fullName = normFirstName + " " + normLastName;
    std::string fullAddress = normStreetNum + " " + normStreetName;
    
    std::vector<SearchResult> results;
    
    // Get exact matches
    auto exactMatches = findExactMatches(fullName, fullAddress);
    results.insert(results.end(), exactMatches.begin(), exactMatches.end());
    
    // Get fuzzy matches if no exact matches found
    if (exactMatches.empty()) {
        auto fuzzyMatches = findFuzzyMatches(fullName, fullAddress, fuzzyThreshold);
        results.insert(results.end(), fuzzyMatches.begin(), fuzzyMatches.end());
    }
    
    return results;
}

// Python bindings
PYBIND11_MODULE(voter_matcher, m) {
    py::class_<VoterRecord, std::shared_ptr<VoterRecord>>(m, "VoterRecord")
        .def_readonly("vsn", &VoterRecord::vsn)
        .def_readonly("party", &VoterRecord::party)
        .def_readonly("first_name", &VoterRecord::firstName)
        .def_readonly("last_name", &VoterRecord::lastName)
        .def_readonly("street_number", &VoterRecord::streetNumber)
        .def_readonly("street_name", &VoterRecord::streetName);

    py::enum_<SearchResult::MatchType>(m, "MatchType")
        .value("EXACT", SearchResult::MatchType::EXACT)
        .value("ADDRESS_ONLY", SearchResult::MatchType::ADDRESS_ONLY)
        .value("FUZZY_NAME", SearchResult::MatchType::FUZZY_NAME)
        .value("FUZZY_ADDRESS", SearchResult::MatchType::FUZZY_ADDRESS);

    py::class_<SearchResult>(m, "SearchResult")
        .def_readonly("type", &SearchResult::type)
        .def_readonly("score", &SearchResult::score)
        .def_readonly("record", &SearchResult::record);

    py::class_<VoterDatabase>(m, "VoterDatabase")
        .def(py::init<>())
        .def("load_voter_data", &VoterDatabase::loadVoterData)
        .def("find_matches", &VoterDatabase::findMatches);
}
